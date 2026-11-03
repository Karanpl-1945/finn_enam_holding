"""Serve FINN's web app and existing research API on one local address."""
import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
# Set this before importing the serverless handler, which defaults to /tmp.
os.environ.setdefault("FINN_DATA_DIR", str(ROOT / "data"))

from api.research import handler as ResearchHandler  # noqa: E402


class LocalHandler(ResearchHandler, SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/research":
            return ResearchHandler.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), LocalHandler)
    except OSError as exc:
        parser.exit(1, f"Could not start FINN on port {args.port}: {exc}\n")
    print(f"FINN: http://127.0.0.1:{server.server_port}", flush=True)
    print("Press Ctrl+C to stop. Prepared reports use the existing cache.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
