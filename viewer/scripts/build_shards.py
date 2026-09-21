#!/usr/bin/env python3

import os
import sys
import json
from collections import defaultdict
from dotenv import load_dotenv

# --- Load env ---------------------------------------------------

load_dotenv()

base_dir = os.getenv("IMAGE_DATA_PATH", "./data/Delivery")

if not os.path.exists(base_dir):
    raise SystemExit(f"IMAGE_DATA_PATH does not exist: {base_dir}")

# --- Target environment ----------------------------------------

if len(sys.argv) not in (2, 3):
    print("Usage: build_shards.py [local|stage|prod] [subpath]")
    print("  subpath: optional, relative to IMAGE_DATA_PATH — scan only this")
    print("           directory instead of the whole tree (e.g. a new batch's")
    print("           folder), for a much faster incremental update.")
    sys.exit(1)

target = sys.argv[1]

if target not in ["local", "stage", "prod"]:
    print("Target must be one of: local, stage, prod")
    sys.exit(1)

output_dir = os.path.join("viewer", target, "idx")
os.makedirs(output_dir, exist_ok=True)

scan_root = os.path.join(base_dir, sys.argv[2]) if len(sys.argv) == 3 else base_dir
if not os.path.exists(scan_root):
    raise SystemExit(f"Path does not exist: {scan_root}")

# --- Build shards ----------------------------------------------


def shard_key_for(key: str) -> str:
    """First 4 digits after the literal ID prefix — must match shardKeyFor()
    in viewer/*/index.html, or shard lookups break.

    A plain 7-char slice (used before) puts every "GB-Folder_..." label in
    the same "GB-Fold" bucket, since "GB-Folder_" is itself a 10-char
    literal — unlike "GB-" + digits, it never varies in its first 7 chars.
    Folder labels are ~13% of Picturae's own delivery (98,765 of 752,734
    rows), not a rare edge case, so they need to spread across shards too.
    """
    if key.startswith("GB-Folder_"):
        return key[:14]  # "GB-Folder_" (10 chars) + 4 digits
    return key[:7]        # "GB-" (3 chars) + 4 digits


shards = defaultdict(dict)
total_files = 0

for root, _, files in os.walk(scan_root):
    for file in files:
        if not file.endswith(".jp2"):
            continue

        key = os.path.splitext(file)[0]   # GB-0500017 or GB-Folder_0018345
        shard_key = shard_key_for(key)    # GB-0500     or GB-Folder_0018

        relative_path = os.path.relpath(root, base_dir)
        relative_path = relative_path.replace("\\", "/")

        shards[shard_key][key] = relative_path
        total_files += 1

# --- Write output ------------------------------------------------
# Merge into each shard file rather than overwrite it: a partial scan_root
# only ever sees a subset of the images that belong to a given shard key, so
# blindly overwriting would drop every entry found by earlier runs outside
# this subpath. This also means a shard file never sheds entries for images
# that were deleted from disk since the last full (no-subpath) run — run
# without a subpath occasionally to clear those out.

for shard_key, entries in shards.items():
    shard_path = os.path.join(output_dir, f"{shard_key}.json")

    existing = {}
    if os.path.exists(shard_path):
        with open(shard_path, encoding="utf-8") as f:
            existing = json.load(f)

    # len(entries) is every file this run's walk found under scan_root — that's
    # not the same as how many are actually new to the shard, since a partial
    # rerun walks the same files again every time. Diff against what was
    # already on disk so the count means what it says.
    changed_count = sum(1 for k, v in entries.items() if existing.get(k) != v)
    existing.update(entries)

    with open(shard_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"{shard_path} → {len(existing)} entries "
          f"({changed_count} new/changed, {len(entries)} scanned this run)")

print(f"\nTotal {total_files} .jp2 files found under {scan_root}, "
      f"split into {len(shards)} shard(s)")
