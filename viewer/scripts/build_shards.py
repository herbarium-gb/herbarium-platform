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

if len(sys.argv) != 2:
    print("Usage: build_shards.py [local|stage|prod]")
    sys.exit(1)

target = sys.argv[1]

if target not in ["local", "stage", "prod"]:
    print("Target must be one of: local, stage, prod")
    sys.exit(1)

output_dir = os.path.join("viewer", target, "idx")
os.makedirs(output_dir, exist_ok=True)

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

for root, _, files in os.walk(base_dir):
    for file in files:
        if not file.endswith(".jp2"):
            continue

        key = os.path.splitext(file)[0]   # GB-0500017 or GB-Folder_0018345
        shard_key = shard_key_for(key)    # GB-0500     or GB-Folder_0018

        relative_path = os.path.relpath(root, base_dir)
        relative_path = relative_path.replace("\\", "/")

        shards[shard_key][key] = relative_path
        total_files += 1

# --- Write output ----------------------------------------------

for shard_key, entries in shards.items():
    shard_path = os.path.join(output_dir, f"{shard_key}.json")

    with open(shard_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"{shard_path} → {len(entries)} entries")

print(f"\nTotal {total_files} .jp2 files split into {len(shards)} shard(s)")
