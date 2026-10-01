#!/usr/bin/env python3
"""
Batch download of herbarium images.

Usage:
  python batch_download.py ids.txt [options]

ids.txt should contain one GB-ID per line, e.g.:
  GB-0500017
  GB-0500018

Options:
  --base-url URL    Base URL of the herbarium viewer (required)
  --out DIR         Output directory (default: ./downloads)
  --workers N       Parallel downloads (default: 4)
"""

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlretrieve

VALID_GB_ID = re.compile(r"^GB-\d{7}$")
EXTRACT_GB_ID = re.compile(r"(GB-\d{7})")


def load_ids(path: str) -> list[str]:
    ids = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = EXTRACT_GB_ID.search(line)
            if not m:
                print(f"  [skip] no GB-ID found: {line!r}", flush=True)
                continue
            ids.append(m.group(1))
    return ids


def download_one(image_id: str, base_url: str, out_dir: Path) -> tuple[str, bool, str]:
    dest = out_dir / f"{image_id}.jpg"
    if dest.exists():
        return image_id, True, "already exists"
    try:
        url = f"{base_url}/{image_id}.jpg"
        urlretrieve(url, dest)
        return image_id, True, str(dest)
    except Exception as e:
        return image_id, False, str(e)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids_file", help="Text file with one GB-ID per line")
    parser.add_argument("--base-url", required=True,
                        help="Base URL of the IIIF viewer, e.g. https://botmus.gu.se")
    parser.add_argument("--out", default="downloads",
                        help="Output directory (default: ./downloads)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel downloads (default: 4)")
    args = parser.parse_args()

    ids = load_ids(args.ids_file)
    if not ids:
        print("No valid GB-IDs found in file.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(ids)} image(s) → {out_dir}/")
    print(f"Base URL: {args.base_url}  |  Workers: {args.workers}\n")

    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download_one, id_, args.base_url, out_dir): id_
            for id_ in ids
        }
        for future in as_completed(futures):
            image_id, success, msg = future.result()
            if success:
                ok += 1
                print(f"  [ok]   {image_id}  →  {msg}", flush=True)
            else:
                fail += 1
                print(f"  [err]  {image_id}  —  {msg}", flush=True)

    print(f"\nDone: {ok} succeeded, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
