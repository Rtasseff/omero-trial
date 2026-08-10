"""Copy the manifest's acquisition folders from J:\ (read-only source) to D:\.

Mirrors the raw structure minus the /raw prefix:
  J:\gjesus3-data\raw\MICROSCOPY\2026\2026-06\ACQ-...\  ->  data\MICROSCOPY\2026\2026-06\ACQ-...\
Verifies file counts/sizes after copy and clears nothing on the source.

Run from Windows:  python copy_subset.py
"""
import csv
import shutil
from pathlib import Path

NAS_ROOT = Path(r"J:\gjesus3-data")
BASE = Path(__file__).resolve().parent.parent
MANIFEST = BASE / "manifest" / "subset_manifest.csv"
DATA = BASE / "data"

copied = skipped = 0
with open(MANIFEST, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rel = r["canonical_path"].strip("/")          # raw/MICROSCOPY/2026/...
        assert rel.startswith("raw/"), rel
        src = NAS_ROOT / rel.replace("/", "\\")
        dst = DATA / rel[len("raw/"):].replace("/", "\\")
        if dst.exists():
            skipped += 1
            continue
        shutil.copytree(src, dst)
        n_src = sum(1 for p in src.rglob("*") if p.is_file())
        n_dst = sum(1 for p in dst.rglob("*") if p.is_file())
        b_src = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
        b_dst = sum(p.stat().st_size for p in dst.rglob("*") if p.is_file())
        if (n_src, b_src) != (n_dst, b_dst):
            raise SystemExit(f"MISMATCH after copy: {src} ({n_src},{b_src}) vs ({n_dst},{b_dst})")
        copied += 1
        print(f"ok  {r['acq_id']}  {b_dst/1e6:.0f} MB")

print(f"done: {copied} copied, {skipped} already present")
