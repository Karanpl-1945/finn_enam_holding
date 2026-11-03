"""Run the existing fetch CLI with the working local Yahoo HTTP backend."""
import os
from pathlib import Path


def main():
    # curl_cffi times out on this computer; yfinance supports requests too.
    # Set this before importing yfinance. An explicit environment value wins.
    os.environ.setdefault("YF_DISABLE_CURL_CFFI", "1")

    import yfinance as yf

    cache = Path(__file__).resolve().parent / ".venv" / "yfinance-cache"
    yf.set_tz_cache_location(str(cache))

    from fetch_all import main as fetch_main

    fetch_main()


if __name__ == "__main__":
    main()
