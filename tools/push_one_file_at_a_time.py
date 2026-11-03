"""Preview, or publish one file per commit and one commit per push.

Preview: python tools/push_one_file_at_a_time.py
Publish: python tools/push_one_file_at_a_time.py --important-only --execute

Uses the configured Git author and current timestamps. Ignored files stay
excluded. A failed push stops the process; rerunning resumes pending commits.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".venv" / "git-publish"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "--no-optional-locks"]
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}
for variable in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
    ENV.pop(variable, None)


def configured_keys():
    keys = [os.environ.get("GEMINI_API_KEY", "")]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "GEMINI_API_KEY":
                keys.append(value.strip().strip("\"'"))
    return [key for key in keys if key]


KEYS = configured_keys()


def redact(value):
    for key in KEYS:
        value = value.replace(key, "[REDACTED]")
    return re.sub(r"(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)


def git(*args, allow_failure=False, network=False):
    result = subprocess.run(
        GIT + list(args), cwd=ROOT, env=ENV, capture_output=True,
        encoding="utf-8", errors="replace", timeout=120 if network else 60,
    )
    if result.returncode and not allow_failure:
        raise RuntimeError(redact(result.stderr.strip() or result.stdout.strip()))
    return result


def paths(output):
    return [name for name in output.split("\0") if name]


def section(name):
    if name in {".gitignore", ".vercelignore", "web/.gitignore", "requirements.txt", "config.py"}:
        return "01-configuration"
    if name.startswith("finn/"):
        return "02-core"
    if name.startswith("api/"):
        return "03-api"
    if name.endswith(".py") and "/" not in name:
        return "04-local-commands"
    if name.startswith("tests/"):
        return "05-tests"
    if name.startswith("data/prices/"):
        return "06-price-data"
    if name.startswith("data/announcements/"):
        return "07-announcements"
    if name.startswith("data/fundamentals/"):
        return "08-fundamentals"
    if name.startswith("data/research/"):
        return "09-research-data"
    if name.startswith("data/results/"):
        return "10-results-data"
    if name.startswith("web/") or name == "vercel.json":
        return "11-web"
    if name.endswith(".md"):
        return "12-documentation"
    return "13-tools"


def important_file(name):
    root_files = {
        ".gitignore", ".vercelignore", "README.md", "requirements.txt",
        "config.py", "fetch_all.py", "export_web.py", "research.py",
        "run_local.py", "refresh_local.py", "vercel.json",
    }
    return (name in root_files
            or name.startswith(("finn/", "api/", "tests/", "web/"))
            or name in {"docs/LOCAL_SETUP.md", "tools/push_one_file_at_a_time.py"})


def verify_file(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unexpected path: {name}")
    if any(part in {".git", ".venv", ".vercel", "__pycache__"} for part in path.parts):
        raise RuntimeError(f"Local-only file would be included: {name}")
    if path.name.startswith(".env") or name == "docs/brief.md":
        raise RuntimeError(f"Excluded file would be included: {name}")
    content = (ROOT / name).read_bytes()
    if any(key.encode() in content for key in KEYS):
        raise RuntimeError(f"An API key was detected in {name}; nothing from this plan will be pushed.")
    patterns = (
        rb"AIza[0-9A-Za-z_-]{30,50}",
        rb"gh[pousr]_[0-9A-Za-z]{30,}",
        rb"github_pat_[0-9A-Za-z_]{40,}",
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    )
    if any(re.search(pattern, content) for pattern in patterns):
        raise RuntimeError(f"A possible credential was detected in {name}.")
    return hashlib.sha256(content).hexdigest()


def one_file_commit(commit):
    names = paths(git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit).stdout)
    if len(names) != 1:
        raise RuntimeError(f"Commit {commit[:12]} changes {len(names)} files; refusing to push it.")
    return names[0]


def log(event, show=True, **fields):
    item = {"event": event, **fields}
    line = json.dumps(item, ensure_ascii=True)
    with (STATE / "progress.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    if show:
        print(line, flush=True)


def publish(remote, branch, plan, pending, important_only=False):
    total = len(plan) + len(pending)
    completed = 0

    def push(commit, name):
        nonlocal completed
        one_file_commit(commit)
        git("push", remote, f"{commit}:refs/heads/{branch}", network=True)
        completed += 1
        log("file_pushed", show=completed == 1 or completed % 10 == 0 or completed == total,
            completed=completed, total=total, file=name, commit=commit)

    for commit in pending:
        push(commit, one_file_commit(commit))
    for item in plan:
        name = item["file"]
        if verify_file(name) != item["sha256"]:
            raise RuntimeError(f"{name} changed after the preview. Rerun to create a fresh plan.")
        if paths(git("diff", "--cached", "--name-only", "-z").stdout):
            raise RuntimeError("The index contains another change; stopping before staging a file.")
        git("add", "--", name)
        staged = paths(git("diff", "--cached", "--name-only", "-z").stdout)
        if staged != [name]:
            raise RuntimeError(f"Expected exactly {name} in the index; found {staged}.")
        git("commit", "-m", item["message"])
        commit = git("rev-parse", "HEAD").stdout.strip()
        if one_file_commit(commit) != name:
            raise RuntimeError("The commit contents differ from the planned file; stopping before pushing.")
        log("file_committed", show=False, file=name, commit=commit)
        push(commit, name)
    git("branch", f"--set-upstream-to={remote}/{branch}", branch)
    local = git("rev-parse", "HEAD").stdout.strip()
    reference = git("ls-remote", "--heads", remote, f"refs/heads/{branch}", network=True).stdout.split()
    if not reference or reference[0] != local:
        raise RuntimeError("The final remote revision does not match the local revision.")
    remaining = set(paths(git("ls-files", "--others", "--modified", "--exclude-standard", "-z").stdout))
    selected_remaining = {name for name in remaining if important_file(name)} if important_only else remaining
    if selected_remaining:
        raise RuntimeError("Publishing finished, but selected files have further local changes to review.")
    log("complete", files_pushed=completed, branch=branch, revision=local,
        selected_files_clean=True, remaining_unpublished_files=len(remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="commit and push each file; otherwise preview only")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--important-only", action="store_true",
                        help="publish runnable source, tests, setup docs and static demo assets; exclude raw caches and internal notes")
    parser.add_argument("--expected-origin", help="stop unless the configured destination exactly matches this URL")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    if git("branch", "--show-current").stdout.strip() != args.branch:
        raise RuntimeError(f"Switch to the intended branch {args.branch} before running this script.")
    if paths(git("diff", "--cached", "--name-only", "-z").stdout):
        raise RuntimeError("There are already staged changes. The script will not unstage them.")
    git("var", "GIT_AUTHOR_IDENT")
    git("var", "GIT_COMMITTER_IDENT")
    origin = git("remote", "get-url", args.remote).stdout.strip()
    if args.expected_origin and origin != args.expected_origin:
        raise RuntimeError("The configured remote differs from the explicitly selected destination.")
    remote_refs = git("ls-remote", "--heads", args.remote, f"refs/heads/{args.branch}", network=True).stdout.split()
    remote_head = remote_refs[0] if remote_refs else None
    head = git("rev-parse", "--verify", "HEAD", allow_failure=True)
    has_head = head.returncode == 0
    if remote_head and not has_head:
        raise RuntimeError("The remote has existing history; this empty local repository needs to be reconciled first.")
    if remote_head:
        if git("cat-file", "-e", f"{remote_head}^{{commit}}", allow_failure=True).returncode:
            git("fetch", "--no-tags", args.remote, f"refs/heads/{args.branch}", network=True)
        if git("merge-base", "--is-ancestor", remote_head, "HEAD", allow_failure=True).returncode:
            raise RuntimeError("Local and remote history diverged. No force push will be used.")
    pending = []
    if has_head:
        pending = git("rev-list", "--reverse", f"{remote_head}..HEAD" if remote_head else "HEAD").stdout.split()
        for commit in pending:
            name = one_file_commit(commit)
            if args.important_only and not important_file(name):
                raise RuntimeError(f"Pending commit {commit[:12]} includes a file outside the important selection: {name}")
    tracked = set(paths(git("ls-files", "-z").stdout))
    candidates = set(paths(git("ls-files", "--others", "--modified", "--exclude-standard", "-z").stdout))
    if args.important_only:
        candidates = {name for name in candidates if important_file(name)}
    ordered = sorted(candidates, key=lambda name: (section(name), name != ".gitignore", name))
    plan = [{"file": name, "section": section(name), "sha256": verify_file(name),
             "message": f"{'Update' if name in tracked else 'Add'} {name}"} for name in ordered]
    manifest = {"branch": args.branch, "remote": args.remote, "destination": redact(origin),
                "important_only": args.important_only, "files": plan, "pending_commits": pending}
    (STATE / "plan.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log("plan", files=len(plan), pending_commits=len(pending),
        sections=dict(Counter(item["section"] for item in plan)), execute=args.execute)
    if not args.execute or not plan and not pending:
        return
    lock = STATE / "publish.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        publish(args.remote, args.branch, plan, pending, important_only=args.important_only)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(json.dumps({"event": "stopped", "error": redact(str(exc))}), flush=True)
        sys.exit(1)
