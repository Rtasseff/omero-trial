"""Bulk in-place import of the gjesus3 MICROSCOPY mirror into OMERO.

Reads the registry snapshot (manifest/registry_raw.csv on D:), imports every
MICROSCOPY acquisition whose file exists in the mirror and which is not already
recorded in manifest/import_map.csv. Safe to re-run: already-imported acqs are
skipped, previously FAILED ones are retried, files the mirror hasn't delivered
yet are left for the next run.

OMERO layout: one Project per gjesus3 project (PROJ-00xx · name), one Dataset
per instrument inside it.

Run inside WSL:  python3 import_all.py
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_HOME = Path("/mnt/d/projects/gjesus3-tools/omero-trial")
REGISTRY = DATA_HOME / "manifest" / "registry_raw.csv"
PROJECTS = DATA_HOME / "manifest" / "registry_projects.csv"
IMPORT_MAP = DATA_HOME / "manifest" / "import_map.csv"

creds = {}
for f in (".env", "accounts.env"):
    for line in (REPO / f).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()

OMERO = ["docker", "exec", "omero-trial_omeroserver_1",
         "/opt/omero/server/venv3/bin/omero"]
AUTH = ["-s", "localhost", "-u", creds["OMERO_IMPORTER_USER"],
        "-w", creds["OMERO_IMPORTER_PASS"]]

def omero(*args, check=True):
    r = subprocess.run(OMERO + list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"omero {' '.join(args[:3])}... failed:\n{r.stderr[-2000:]}")
    return r

def hql(query):
    out = omero("hql", *AUTH, "-q", "--style", "plain", "--limit", "5000", query).stdout
    rows_ = []
    for line in out.splitlines():
        parts = line.split(",", 3)
        if len(parts) >= 2 and parts[0].strip().isdigit():
            rows_.append([p.strip() for p in parts[1:]])
    return rows_

proj_names = {}
with open(PROJECTS, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        proj_names[r["project_id"]] = r["name"]

rows = [r for r in csv.DictReader(open(REGISTRY, newline="", encoding="utf-8"))
        if r["data_ecosystem"] == "MICROSCOPY"]

# import_map: done acqs are skipped, FAILED rows dropped (retried below)
done = set()
kept = []
if IMPORT_MAP.exists():
    for r in csv.DictReader(open(IMPORT_MAP, newline="", encoding="utf-8")):
        if r["image_ids"] != "FAILED":
            done.add(r["acq_id"])
            kept.append(r)
with open(IMPORT_MAP, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["acq_id", "image_ids"])
    w.writeheader()
    w.writerows(kept)

# existing OMERO Projects/Datasets (reuse across runs)
proj_ids, ds_ids = {}, {}
for oid, name in hql("select p.id, p.name from Project p"):
    proj_ids[name.split(" · ")[0]] = oid
for parent, child, name in hql(
        "select l.parent.name, l.child.id, l.child.name from ProjectDatasetLink l"):
    ds_ids[(parent.split(" · ")[0], name)] = child

def dataset_for(r):
    pid = r["project_id"] or "PROJ-none"
    if pid not in proj_ids:
        label = f"{pid} · {proj_names.get(pid, 'unassigned')}"
        out = omero("obj", *AUTH, "new", "Project", f"name={label}").stdout.strip()
        proj_ids[pid] = out.split(":")[1]
        print(f"Project {label} -> {out}", flush=True)
    key = (pid, r["instrument"])
    if key not in ds_ids:
        out = omero("obj", *AUTH, "new", "Dataset", f"name={r['instrument']}").stdout.strip()
        ds_ids[key] = out.split(":")[1]
        omero("obj", *AUTH, "new", "ProjectDatasetLink",
              f"parent=Project:{proj_ids[pid]}", f"child=Dataset:{ds_ids[key]}")
    return ds_ids[key]

todo = [r for r in rows if r["acq_id"] not in done]
print(f"{len(rows)} microscopy acqs in registry; {len(done)} already imported; "
      f"{len(todo)} to do", flush=True)

ok = fail = missing = 0
with open(IMPORT_MAP, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    for i, r in enumerate(todo, 1):
        rel = r["canonical_path"].lstrip("/")[len("raw/"):]   # MICROSCOPY/.../ACQ-x/
        host_file = DATA_HOME / "data" / rel / r["primary_file_name"]
        if not host_file.exists():
            missing += 1                    # mirror not there yet; next run gets it
            continue
        path = f"/gjesus3-data/{rel}{r['primary_file_name']}"
        res = omero("import", *AUTH, "-T", f"Dataset:id:{dataset_for(r)}",
                    "--transfer=ln_s", "--skip=upgrade", path, check=False)
        images = sorted(set(re.findall(r"Image:([\d,]+)", res.stdout)))
        if res.returncode != 0 or not images:
            fail += 1
            w.writerow([r["acq_id"], "FAILED"]); f.flush()
            print(f"[{i}/{len(todo)}] FAIL {r['acq_id']}: "
                  f"{res.stderr.strip().splitlines()[-1] if res.stderr.strip() else 'no output'}",
                  flush=True)
            continue
        ok += 1
        w.writerow([r["acq_id"], ";".join(images)]); f.flush()
        if ok % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] {ok} ok, {fail} failed, {missing} not in mirror yet",
                  flush=True)

print(f"import_all done: {ok} imported, {fail} failed, {missing} awaiting mirror",
      flush=True)
sys.exit(1 if fail else 0)
