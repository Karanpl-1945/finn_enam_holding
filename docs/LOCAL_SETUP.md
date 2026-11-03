
`git remote add origin https://github.com/Karanpl-1945/finn_enam_holding.git`# Running FINN on Windows

Run these PowerShell commands from the `FINN` folder. Use the virtual
environment's Python directly; activation is optional.

## GitHub package

The important-files publication includes the source, tests, local launchers,
this setup guide, and the exported demo snapshot under `web/data/`. Raw
`data/` caches, extracted transcripts, internal handoff notes, `.env`, and
local environments stay on the local computer.

On a fresh clone, the Today tab and prepared Research reports use
`web/data/`. Direct API requests generate and cache a report locally when
there is no corresponding raw `data/research/` review. That needs the Gemini
key and access to the source websites. Fetch raw prices and announcements
before regenerating the web feed; prepare any desired research reports with
`research.py` before exporting their index.

## Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

If pip makes no progress, the available `uv` installer can install the same
requirements into the same environment:

```powershell
uv pip install --python .\.venv\Scripts\python.exe --cache-dir .\.venv\.uv-cache -r requirements.txt
```

## Configure Gemini

Open `.env` in the `FINN` folder and save your own key:

```dotenv
GEMINI_API_KEY=your_actual_key
```

The existing `.gitignore` excludes `.env` and `.venv`. Prepared reports
and the Today tab do not need a key. New research and results extraction
need a working Gemini key and available quota.

The existing client reads `GEMINI_API_KEY` from `.env` when needed. Other
settings are read from process environment variables. To override the
research model, set it in PowerShell before starting the server:

```powershell
$env:GEMINI_REASONING_MODEL = "gemini-3.8-flash"
```

## Start the app and research API

```powershell
.\.venv\Scripts\python.exe -B run_local.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Keep the command running; press Ctrl+C to stop.
If port 8000 is occupied, add `--port 8001` and open that port instead.

`run_local.py` serves `web/` and routes `/api/research` to the existing
`api/research.py` handler. It defaults `FINN_DATA_DIR` to this project's
`data/` directory so the serverless `/tmp` path is not used on Windows.
Existing prepared reports are reused. New ticker research can download
documents, call Gemini, and save its results under `data/`.

The server binds to this computer only. Only `web/` is served as static
content; the project `.env` is outside that directory.

To check the existing cached TCS report from another PowerShell window:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/research?symbol=TCS'
```

## Refresh data when needed

The included data is a snapshot. Refreshing writes the corresponding cache
files. Check one company first:

```powershell
.\.venv\Scripts\python.exe -X utf8 refresh_local.py --only prices --symbols TCS
.\.venv\Scripts\python.exe -X utf8 refresh_local.py --only announcements --symbols TCS --days 7
```

After a successful check, refresh the portfolio and update the static feed:

```powershell
.\.venv\Scripts\python.exe -X utf8 refresh_local.py --only prices
.\.venv\Scripts\python.exe -X utf8 refresh_local.py --only announcements --days 5
.\.venv\Scripts\python.exe -X utf8 export_web.py
```

`refresh_local.py` forwards the same options to the original `fetch_all.py`.
On this computer, yfinance's default `curl_cffi` backend times out resolving
Yahoo hosts, while its supported `requests` backend works. The launcher sets
`YF_DISABLE_CURL_CFFI=1` for that process and keeps Yahoo's cookie/timezone
cache inside `.venv/yfinance-cache/`. It does not change the fetcher code.
The library may print a fallback warning; `curl_cffi` is still installed.
To try the default backend again, set `$env:YF_DISABLE_CURL_CFFI = "0"`
before running the launcher.

To extract results or prepare research through the CLI:

```powershell
.\.venv\Scripts\python.exe -X utf8 refresh_local.py --only results --symbols TCS
.\.venv\Scripts\python.exe -X utf8 research.py TCS
.\.venv\Scripts\python.exe -X utf8 export_web.py
```

Research reuses saved reviews. After new transcripts appear, add `--refresh`
to the research command, then run `export_web.py` again.

The original `docs/brief.md` and source PDFs are deliberately excluded from
Git. The original brief is not needed to run the app. Existing transcript
text is included, and downloads occur when new documents are needed.

## Verified on 3 November 2026

- All five required packages and NumPy import successfully; `pip check` passes.
- All 25 offline tests pass.
- Prices refreshed for all 18 portfolio companies through 3 November.
- NSE refresh succeeded for all 18 companies; the exported feed has 281 filings.
- Fundamentals refreshed for INFY, ASIANPAINT, IRCTC and KAYNES.
- A new TITAN research request completed through the local API, analyzing
  four transcripts with Gemini. There are now 14 prepared research reports.
- Asian Paints research was regenerated to include its new November 2026
  transcript. All saved reviews use the latest four calls available locally.
- The JavaScript rendered Today and all 14 research reports in a DOM smoke
  check. The static files and cached research API respond over local HTTP.
- The original application code, README and requirements remain unchanged.

The data before this refresh is backed up under `.venv/backups/`. The file
`.venv/last-refresh-backup.txt` records the backup directory. Verification
details are saved in `.venv/live-checks/final-verification.json`.
