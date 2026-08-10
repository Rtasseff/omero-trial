"""Select a representative microscopy subset for the OMERO trial.

Reads the live gjesus3 registry (read-only), picks acquisitions per instrument
with rich metadata (project_id + anatomical_entity set), concentrated in the
projects that hold the most microscopy, and writes the full registry rows of
the chosen acquisitions to manifest/subset_manifest.csv.

Run from Windows:  python select_subset.py
"""
import csv
from collections import defaultdict
from pathlib import Path

REGISTRY = r"J:\gjesus3-data\registries\registry_raw.csv"
OUT = Path(__file__).resolve().parent.parent / "manifest" / "subset_manifest.csv"

# per-instrument picks: (max_count, per-file size window in MB)
PLAN = {
    "LSM9": (15, (1, 2500)),
    "CELL": (12, (10, 2000)),
    "ZWSI": (4, (200, 1500)),
}
TOTAL_CAP_MB = 26_000

rows = []
with open(REGISTRY, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["data_ecosystem"] != "MICROSCOPY":
            continue
        try:
            r["_mb"] = float(r["file_size_mb"] or 0)
        except ValueError:
            r["_mb"] = 0.0
        rows.append(r)

# rank projects by microscopy acquisition count
per_proj = defaultdict(int)
for r in rows:
    if r["project_id"]:
        per_proj[r["project_id"]] += 1
top_projects = {p for p, _ in sorted(per_proj.items(), key=lambda kv: -kv[1])[:6]}

def score(r):
    s = 0
    if r["project_id"] in top_projects: s += 4
    if r["project_id"]: s += 2
    if r["anatomical_entity"]: s += 2
    if r["researcher"]: s += 1
    if r["sample_organism"]: s += 1
    return (-s, r["acq_id"])  # tie-break: stable, favours older=varied dates

picked, total = [], 0.0
for inst, (max_n, (lo, hi)) in PLAN.items():
    cands = sorted((r for r in rows if r["instrument"] == inst and lo <= r["_mb"] <= hi), key=score)
    # spread across projects: at most 4 per project per instrument
    per_p = defaultdict(int)
    for r in cands:
        if len([p for p in picked if p["instrument"] == inst]) >= max_n:
            break
        if per_p[r["project_id"]] >= 4:
            continue
        if total + r["_mb"] > TOTAL_CAP_MB:
            continue
        picked.append(r); per_p[r["project_id"]] += 1; total += r["_mb"]

OUT.parent.mkdir(parents=True, exist_ok=True)
fields = [k for k in picked[0].keys() if k != "_mb"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in picked:
        w.writerow(r)

print(f"picked {len(picked)} acqs, {total/1024:.1f} GB -> {OUT}")
for inst in PLAN:
    sub = [r for r in picked if r["instrument"] == inst]
    projs = sorted({r['project_id'] or '-' for r in sub})
    print(f"  {inst}: {len(sub)} acqs, {sum(r['_mb'] for r in sub)/1024:.1f} GB, projects: {', '.join(projs)}")
