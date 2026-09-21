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
# A run only "owns" entries whose recorded directory is scan_root itself or
# somewhere under it — that's the part of the tree it actually looked at.
# Owned entries not rediscovered this run are genuinely gone and get
# dropped; everything outside scan_root is left completely untouched,
# whether this is a full run (scan_root == base_dir, so it owns everything)
# or a partial one scoped to a single new/changed directory. That makes a
# partial rerun of just a test folder correctly reflect deletions there,
# without needing a slow full-tree rebuild to do it.

scan_relpath = os.path.relpath(scan_root, base_dir).replace("\\", "/")
is_full_run = scan_relpath == "."


def owned_by_this_run(entry_dir: str) -> bool:
    if is_full_run:
        return True
    return entry_dir == scan_relpath or entry_dir.startswith(scan_relpath + "/")


# A shard can hold owned entries this run's walk found nothing for at all
# (e.g. every image that used to be in scan_root got deleted) — checking
# every existing shard file for that is only worth it on a full run (already
# the heavier, occasional pass) or when this run's walk found zero files at
# all (the only situation where a partial run has no other way to know which
# shard(s) it needs to reconcile). A normal partial run with live files stays
# scoped to just the shard(s) those files belong to.
if is_full_run or total_files == 0:
    shard_keys = set(shards) | {n[:-5] for n in os.listdir(output_dir) if n.endswith(".json")}
else:
    shard_keys = set(shards)

for shard_key in sorted(shard_keys):
    shard_path = os.path.join(output_dir, f"{shard_key}.json")
    entries = shards.get(shard_key, {})

    existing = {}
    if os.path.exists(shard_path):
        with open(shard_path, encoding="utf-8") as f:
            existing = json.load(f)

    # Keep anything not owned by this run untouched; an owned entry only
    # survives if this run's walk rediscovered it.
    kept = {k: v for k, v in existing.items() if not owned_by_this_run(v) or k in entries}
    new_content = {**kept, **entries}

    # len(entries) is every file this run's walk found for this shard — not
    # the same as how many are actually new, since a rerun walks the same
    # files again every time. Diff against what was already on disk instead.
    changed_count = sum(1 for k, v in entries.items() if existing.get(k) != v)
    dropped_count = len(existing) - len(kept)

    if new_content:
        with open(shard_path, "w", encoding="utf-8") as f:
            json.dump(new_content, f, indent=2, ensure_ascii=False)
        note = f", {dropped_count} dropped" if dropped_count else ""
        print(f"{shard_path} → {len(new_content)} entries "
              f"({changed_count} new/changed, {len(entries)} scanned this run{note})")
    elif os.path.exists(shard_path):
        os.remove(shard_path)
        print(f"Removed stale shard file (no live images left): {shard_path}")

print(f"\nTotal {total_files} .jp2 files found under {scan_root}, "
      f"split into {len(shards)} shard(s)")
