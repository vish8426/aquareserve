"""Download real SILO daily climate data (fao56 format) for a station.

SILO (Queensland Government Long Paddock) provides free daily Australian climate data from 1889 to yesterday under CC BY 4.0, including FAO-56 Penman-Monteith short-crop reference ET (ET0).
This script fetches the 'fao56' point dataset for a station and saves it where the loader expects it (data/raw/silo_mildura.txt).

Usage:
    python scripts/fetch_silo.py --email you@example.com \
        --station 76031 --start 20000101 --finish 20231231 \
        --out data/raw/silo_mildura.txt

Notes:
  * station 76031 = Mildura Airport (the default validation site).
  * An email is required by SILO as a free contact identifier (password=apirequest).
  * After downloading, set config/climate.example.yaml period end to cover the range.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SILO_ENDPOINT = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/PatchedPointDataset.php"


def build_url(email: str, station: str, start: str, finish: str) -> str:
    params = {
        "format": "fao56",
        "station": station,
        "start": start,
        "finish": finish,
        "username": email,
        "password": "apirequest",
    }
    return f"{SILO_ENDPOINT}?{urllib.parse.urlencode(params)}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download SILO fao56 station data.")
    ap.add_argument("--email", required=True, help="your email (SILO contact id)")
    ap.add_argument("--station", default="76031", help="BoM station number (default: Mildura Airport)")
    ap.add_argument("--start", default="20000101", help="start date yyyymmdd")
    ap.add_argument("--finish", default="20231231", help="finish date yyyymmdd")
    ap.add_argument("--out", default="data/raw/silo_mildura.txt", help="output path")
    args = ap.parse_args(argv)

    url = build_url(args.email, args.station, args.start, args.finish)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Requesting SILO station {args.station} {args.start}-{args.finish} ...")

    # noqa: S310
    with urllib.request.urlopen(url, timeout=120) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    if "essential parameters" in text.lower() or "sorry" in text[:200].lower():
        print("SILO rejected the request:\n" + text[:400], file=sys.stderr)

        return 1

    out.write_text(text, encoding="utf-8")
    n_rows = sum(1 for line in text.splitlines() if line[:8].isdigit())
    
    print(f"Saved {n_rows} daily rows to {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
