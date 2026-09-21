#!/usr/bin/env python3
"""Regression tests for build_shards.py.

Runs the script as a real subprocess against a throwaway temp tree (its own
IMAGE_DATA_PATH and viewer/<target>/idx output dir) — exercises the exact
same code path as production use, not internals that could drift from it.

These scenarios were all found by hand, the slow way, in one afternoon of
build_shards.py changes: a misleading "new" count, a full run that never
dropped deleted images, a partial run that never dropped them either, and
then a partial run that got just as slow as a full one by checking every
shard file to fix that. Each showed up as a real, confusing symptom (a 404
in the viewer, a suspiciously long "new" count) before being understood —
this file exists so the next change doesn't have to relearn them by hand.

Run:  python3 test_build_shards.py
(with the same interpreter/venv used for build_shards.py itself, so
python-dotenv is importable — e.g. viewer/.venv/bin/python)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "build_shards.py"


class ShardBuildTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.images = self.root / "images"
        self.images.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def touch(self, *rel_path: str) -> None:
        p = self.images.joinpath(*rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    def rm(self, *rel_path: str) -> None:
        self.images.joinpath(*rel_path).unlink()

    def run_build(self, subpath: str | None = None) -> str:
        args = [sys.executable, str(SCRIPT), "local"]
        if subpath:
            args.append(subpath)
        result = subprocess.run(
            args, cwd=self.root, env={**os.environ, "IMAGE_DATA_PATH": str(self.images)},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result.stdout

    def shard(self, name: str) -> dict:
        path = self.root / "viewer" / "local" / "idx" / f"{name}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def shard_mtime(self, name: str) -> float:
        return (self.root / "viewer" / "local" / "idx" / f"{name}.json").stat().st_mtime_ns

    # --- basic behavior --------------------------------------------------

    def test_full_run_creates_shards_grouped_by_key(self):
        self.touch("a", "GB-0500017.jp2")
        self.touch("a", "GB-0500018.jp2")
        self.touch("b", "GB-0600001.jp2")
        self.run_build()
        self.assertEqual(self.shard("GB-0500"), {"GB-0500017": "a", "GB-0500018": "a"})
        self.assertEqual(self.shard("GB-0600"), {"GB-0600001": "b"})

    def test_folder_id_labels_get_their_own_shard_spread(self):
        # A plain 7-char slice used to put every "GB-Folder_..." label in the
        # same "GB-Fold" bucket, since "GB-Folder_" is a 10-char literal that
        # never varies in its first 7 chars — unlike "GB-" + digits.
        self.touch("a", "GB-Folder_0018345.jp2")
        self.touch("a", "GB-Folder_0099999.jp2")
        self.run_build()
        self.assertEqual(self.shard("GB-Folder_0018"), {"GB-Folder_0018345": "a"})
        self.assertEqual(self.shard("GB-Folder_0099"), {"GB-Folder_0099999": "a"})

    def test_full_run_is_idempotent(self):
        self.touch("a", "GB-0500017.jp2")
        self.run_build()
        out = self.run_build()
        self.assertIn("0 new/changed", out)
        self.assertNotIn("dropped", out)

    # --- deletions on a full run ------------------------------------------

    def test_full_run_drops_a_deleted_image(self):
        self.touch("a", "GB-0500017.jp2")
        self.touch("a", "GB-0500018.jp2")
        self.run_build()
        self.rm("a", "GB-0500018.jp2")
        self.run_build()
        self.assertEqual(self.shard("GB-0500"), {"GB-0500017": "a"})

    def test_full_run_removes_a_shard_file_left_with_no_images(self):
        self.touch("a", "GB-0500017.jp2")
        self.touch("b", "GB-0600001.jp2")
        self.run_build()
        self.rm("b", "GB-0600001.jp2")
        self.run_build()
        self.assertFalse((self.root / "viewer" / "local" / "idx" / "GB-0600.json").exists())

    # --- partial (subpath) runs -------------------------------------------

    def test_partial_run_does_not_touch_shards_outside_its_subpath(self):
        self.touch("a", "GB-0500017.jp2")
        self.touch("b", "GB-0600001.jp2")
        self.run_build()
        before = self.shard_mtime("GB-0600")
        self.run_build(subpath="a")
        self.assertEqual(self.shard_mtime("GB-0600"), before)

    def test_partial_run_drops_a_deletion_within_its_own_subpath(self):
        self.touch("a", "GB-0500017.jp2")
        self.touch("a", "GB-0500018.jp2")
        self.run_build()
        self.rm("a", "GB-0500018.jp2")
        self.run_build(subpath="a")
        self.assertEqual(self.shard("GB-0500"), {"GB-0500017": "a"})

    def test_partial_run_leaves_a_same_shard_entry_from_another_dir_alone(self):
        # Two directories can share a shard file (same numeric prefix). A
        # partial rescan of just one of them must not touch the other's entry.
        self.touch("a", "GB-0500017.jp2")
        self.touch("c", "GB-0500099.jp2")
        self.run_build()
        self.rm("a", "GB-0500017.jp2")
        self.run_build(subpath="a")
        self.assertEqual(self.shard("GB-0500"), {"GB-0500099": "c"})

    def test_partial_run_reconciles_a_subpath_left_with_zero_images(self):
        # The one case a partial run can't scope its own reconciliation to
        # "shards this run found something for" — it found nothing at all.
        self.touch("a", "GB-0500017.jp2")
        self.touch("b", "GB-0600001.jp2")
        self.run_build()
        self.rm("a", "GB-0500017.jp2")
        self.run_build(subpath="a")
        self.assertFalse((self.root / "viewer" / "local" / "idx" / "GB-0500.json").exists())
        # untouched directory's shard must survive the zero-files fallback
        self.assertEqual(self.shard("GB-0600"), {"GB-0600001": "b"})

    def test_partial_run_new_changed_count_reflects_real_changes_only(self):
        # Regression: this used to report every file the walk found as
        # "new/changed", even ones already recorded identically before.
        self.touch("a", "GB-0500017.jp2")
        self.run_build()
        out = self.run_build(subpath="a")
        self.assertIn("0 new/changed, 1 scanned this run", out)


if __name__ == "__main__":
    unittest.main()
