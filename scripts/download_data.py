"""Download the Olympic history dataset and verify it.

Idempotent: if the file is already present and the checksum matches, this does nothing.

Source
------
TidyTuesday archive, 2021 week 31. That file mirrors the Kaggle dataset "120 years of
Olympic history: athletes and results" by Randi H Griffin, whose underlying records were
scraped from sports-reference.com. The Kaggle copy sits behind a login; this mirror does
not, which is why it is the source of record for this project.

Usage:
    python scripts/download_data.py
    python scripts/download_data.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "olympics.csv"

URL = (
    "https://raw.githubusercontent.com/rfordatascience/tidytuesday/"
    "master/data/2021/2021-07-27/olympics.csv"
)
EXPECTED_SHA256 = "227cb326b8ff4e53819bfe1b6682687713eeb496391be572d74de588c7fa3e69"
EXPECTED_BYTES = 35_911_926


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="redownload even if present")
    args = parser.parse_args()

    if DEST.exists() and not args.force:
        actual = sha256(DEST)
        if actual == EXPECTED_SHA256:
            print(f"already present and verified: {DEST.relative_to(ROOT)}")
            return 0
        print(f"checksum mismatch on existing file, redownloading\n  {actual}", file=sys.stderr)

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, DEST)

    size = DEST.stat().st_size
    actual = sha256(DEST)
    print(f"  bytes    {size:,} (expected {EXPECTED_BYTES:,})")
    print(f"  sha256   {actual}")

    if actual != EXPECTED_SHA256:
        print("FAILED: checksum does not match. The upstream file changed.", file=sys.stderr)
        return 1
    if size != EXPECTED_BYTES:
        print("FAILED: size does not match.", file=sys.stderr)
        return 1

    print("verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
