#!/usr/bin/env python3
"""
Batch download of herbarium images from the IIIF server.

Usage:
  python batch_download.py ids.txt [options]

ids.txt should contain one GB-ID per line, e.g.:
  GB-0500017
  GB-0500018

Options:
  --base-url URL    Base URL of the IIIF viewer (required)
  --size SIZE       'small' (1200px wide JPEG) or 'full' (original resolution JPEG)
                    (default: full)
  --out DIR         Output directory (default: ./downloads)
  --workers N       Parallel downloads (default: 4)
  --idx-dir DIR     Local directory with shard .json files; skips HTTP index lookup
                    when provided (useful for offline/local use)
"""

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError, URLError

SHARD_PREFIX_LEN = 7
VALID_GB_ID = re.compile(r"^GB-\d{7}$")


def load_ids(path: str) -> list[str]:
    ids = []
    with open(path) as f:
        for raw in f:
            id_ = raw.strip()
            if not id_ or id_.startswith("#"):
                continue
            if not VALID_GB_ID.match(id_):
                print(f"  [skip] invalid ID: {id_!r}", flush=True)
                continue
            ids.append(id_)
    return ids


def fetch_shard(base_url: str, shard: str) -> dict:
    url = f"{base_url}/idx/{shard}.json"
    try:
        with urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except (HTTPError, URLError) as e:
        raise RuntimeError(f"Could not fetch shard index {url}: {e}") from e


def load_local_shard(idx_dir: str, shard: str) -> dict:
    path = Path(idx_dir) / f"{shard}.json"
    if not path.exists():
        raise RuntimeError(f"Local shard file not found: {path}")
    with open(path) as f:
        return json.load(f)


_shard_cache: dict[str, dict] = {}
_shard_lock = threading.Lock()


def resolve_path(image_id: str, base_url: str, idx_dir: str | None) -> str | None:
    shard = image_id[:SHARD_PREFIX_LEN]
    with _shard_lock:
        if shard not in _shard_cache:
            if idx_dir:
                _shard_cache[shard] = load_local_shard(idx_dir, shard)
            else:
                _shard_cache[shard] = fetch_shard(base_url, shard)
    return _shard_cache[shard].get(image_id)


def image_url(base_url: str, rel: str, image_id: str, size: str) -> str:
    jp2_base = f"{base_url}/iiif/{rel}/{image_id}.jp2"
    if size == "small":
        return f"{jp2_base}/full/1200,/0/default.jpg"
    return f"{jp2_base}/full/full/0/default.jpg"


def download_one(image_id: str, base_url: str, idx_dir: str | None,
                 size: str, out_dir: Path) -> tuple[str, bool, str]:
    suffix = "small" if size == "small" else "large"
    dest = out_dir / f"{image_id}-{suffix}.jpg"
    if dest.exists():
        return image_id, True, "already exists"

    try:
        rel = resolve_path(image_id, base_url, idx_dir)
        if rel is None:
            return image_id, False, "not found in index"

        url = image_url(base_url, rel, image_id, size)
        urlretrieve(url, dest)
        return image_id, True, str(dest)
    except Exception as e:
        return image_id, False, str(e)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids_file", help="Text file with one GB-ID per line")
    parser.add_argument("--base-url", required=True,
                        help="Base URL of the IIIF viewer, e.g. https://example.org")
    parser.add_argument("--size", choices=["small", "full"], default="full",
                        help="Image size to download (default: full)")
    parser.add_argument("--out", default="downloads",
                        help="Output directory (default: ./downloads)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel downloads (default: 4)")
    parser.add_argument("--idx-dir",
                        help="Local directory containing shard .json index files")
    args = parser.parse_args()

    ids = load_ids(args.ids_file)
    if not ids:
        print("No valid GB-IDs found in file.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(ids)} image(s) [{args.size}] → {out_dir}/")
    print(f"Base URL: {args.base_url}  |  Workers: {args.workers}\n")

    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download_one, id_, args.base_url, args.idx_dir,
                        args.size, out_dir): id_
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
