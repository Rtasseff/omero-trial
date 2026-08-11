"""Assign OMERO image ownership per the gjesus3 rules (Ryan, 2026-08-11):

    owner = registry `researcher`  if that name maps to an OMERO user
       else registry `operator`    if that name maps to an OMERO user
       else the gjesus3 importer

Name matching is case-insensitive and goes through ALIASES first (the naming
system is young; add entries as inconsistencies surface). Projects/datasets
stay owned by the importer for the pilot (BACKLOG B5).

Idempotent + delta-aware against SERVER TRUTH: each run re-resolves every
imported acquisition against the CURRENT OMERO user list, queries the actual
image owners, and chowns only the differences. Adding a new OMERO user later
automatically re-homes their acquisitions on the next run.
manifest/ownership_map.csv is written as a REPORT of the resolved state, never
read back as input. Chown batches never split an acquisition across calls:
Chown2 rejects any request that would split a fileset (multi-scene .czi), and
it rejects the WHOLE call while the CLI still exits 0 - found the hard way.
Runs as step 3 of run_pipeline.sh.

Metadata annotations are NOT affected: `omero chown` transfers the image but
leaves the importer's map-annotation blocks owned by the importer (verified
2026-08-11), so annotate_all's owner-based refresh logic keeps working.

Run inside WSL:  python3 assign_ownership.py
"""
import csv
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_HOME = Path("/mnt/d/projects/gjesus3-tools/omero-trial")
REGISTRY = DATA_HOME / "manifest" / "registry_raw.csv"
IMPORT_MAP = DATA_HOME / "manifest" / "import_map.csv"
LEDGER = DATA_HOME / "manifest" / "ownership_map.csv"

# registry-name -> OMERO login, applied after lowercasing
ALIASES = {
    "mbc": "marta",
}
CHUNK = 400  # image ids per chown call

creds = {}
for f in (".env", "accounts.env"):
    for line in (REPO / f).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()

IMPORTER = creds["OMERO_IMPORTER_USER"]
C = ["docker", "exec", "omero-trial_omeroserver_1", "bash", "-c"]
LOGIN = ("/opt/omero/server/venv3/bin/omero login root@localhost "
         f"-w {creds['OMERO_ROOT_PASS']} -g gjesus3-trial >/dev/null 2>&1")

def omero_sh(cmd, check=True):
    r = subprocess.run(C + [f"{LOGIN} && /opt/omero/server/venv3/bin/omero {cmd}"],
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"omero {cmd[:60]}... failed:\n{r.stderr[-1500:]}")
    return r.stdout

# current OMERO users (logins are lowercase)
users = set()
for line in omero_sh("user list --style plain").splitlines():
    parts = line.split(",")
    if len(parts) > 2 and parts[1].strip():
        users.add(parts[1].strip().lower())
users.discard("guest"); users.discard("root")

def resolve(r):
    for field in ("researcher", "operator"):
        name = ALIASES.get(r.get(field, "").strip().lower(),
                           r.get(field, "").strip().lower())
        if name and name in users:
            return name
    return IMPORTER

reg = {r["acq_id"]: r for r in csv.DictReader(open(REGISTRY, newline="", encoding="utf-8"))}
imported = [r for r in csv.DictReader(open(IMPORT_MAP, newline="", encoding="utf-8"))
            if r["image_ids"] != "FAILED"]

# server truth: current owner of every image
current = {}
for line in omero_sh(
        'hql -q --style plain --limit 100000 '
        '"select i.id, i.details.owner.omeName from Image i"').splitlines():
    parts = line.split(",")
    if len(parts) >= 3 and parts[0].strip().isdigit():
        current[parts[1].strip()] = parts[2].strip()

# what needs to move: per target user, a list of PER-ACQUISITION id groups
to_move = defaultdict(list)      # login -> [[ids of one acq], ...]
new_ledger = {}
unresolved = defaultdict(int)    # names that didn't map, for the report
for row in imported:
    r = reg.get(row["acq_id"])
    if r is None:
        continue
    target = resolve(r)
    new_ledger[row["acq_id"]] = target
    if target == IMPORTER:
        who = (r.get("researcher") or r.get("operator") or "").strip()
        if who:
            unresolved[who.lower()] += 1
    ids = [i for part in row["image_ids"].split(";") for i in part.split(",")]
    stale = [i for i in ids if current.get(i, IMPORTER) != target]
    if stale:
        to_move[target].append(ids)   # whole acq together: never split a fileset

# --- project shells ----------------------------------------------------------
# Verified on this deployment (2026-08-12, Ryan's UI + queries): the webclient
# owner filter selects TOP-LEVEL containers only; an owned project displays its
# full contents regardless of image owners. So giving a researcher their
# project shells makes their default login view land on their projects, whole.
# Rule: shell owner = the researcher with the most resolvable acquisitions in
# the project; none resolvable -> importer. chown --exclude Image moves the
# project + its datasets; the boundary dataset-image links get deleted by
# Chown2 (regardless of who owns the links) and are restored by the repair
# pass below, which is why repair MUST run after this.
proj_votes = defaultdict(lambda: defaultdict(int))
for row in imported:
    r = reg.get(row["acq_id"])
    if r is not None:
        proj_votes[r["project_id"] or "PROJ-none"][resolve(r)] += 1
proj_target = {}
for pid, votes in proj_votes.items():
    named = sorted(((n, u) for u, n in votes.items() if u != IMPORTER), reverse=True)
    proj_target[pid] = named[0][1] if named else IMPORTER

proj_moves = 0
for line in omero_sh(
        'hql -q --style plain --limit 1000 '
        '"select p.id, p.details.owner.omeName, p.name from Project p"').splitlines():
    parts = line.split(",", 3)
    if len(parts) < 4 or not parts[0].strip().isdigit():
        continue
    oid, owner, name = parts[1].strip(), parts[2].strip(), parts[3].strip()
    if not name.startswith("PROJ-"):
        continue          # personal 'All <user> data' projects are not vote-managed
    target = proj_target.get(name.split(" · ")[0], IMPORTER)
    if owner != target:
        out = omero_sh(f"chown {target} Project:{oid} --exclude Image 2>&1", check=False)
        if "ok" not in out:
            print(f"WARN project chown {name} -> {target}: {out.strip()[-300:]}", flush=True)
        else:
            print(f"project {name} -> {target}", flush=True)
            proj_moves += 1
if proj_moves == 0:
    print("project shells already current", flush=True)

moved = 0
for login, groups in sorted(to_move.items()):
    batch = []
    def flush():
        global moved
        if not batch:
            return
        out = omero_sh(f"chown {login} Image:{','.join(batch)} 2>&1", check=False)
        if "ok" not in out:
            print(f"WARN chown to {login} reported: {out.strip()[-300:]}", flush=True)
        moved += len(batch)
        del batch[:]
    for ids in groups:
        if batch and len(batch) + len(ids) > CHUNK:
            flush()
        batch.extend(ids)
    flush()
    print(f"{login}: {sum(len(g) for g in groups)} images", flush=True)
if not to_move:
    print("nothing to move - ownership already current", flush=True)

with open(LEDGER, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["acq_id", "owner"])
    for acq, owner in sorted(new_ledger.items()):
        w.writerow([acq, owner])

from collections import Counter
dist = Counter(new_ledger.values())
print("ownership distribution:", dict(sorted(dist.items(), key=lambda kv: -kv[1])), flush=True)
if unresolved:
    top = sorted(unresolved.items(), key=lambda kv: -kv[1])[:12]
    print("unmapped names (add OMERO users or ALIASES to claim):",
          ", ".join(f"{n} x{c}" for n, c in top), flush=True)

# chown removed the giver's dataset links from every transferred image (that is
# how Chown2 works) - restore the tree with root-owned links (see repair_links.py)
def dcp(src, dst):
    subprocess.run(["docker", "cp", str(src), f"omero-trial_omeroserver_1:{dst}"], check=True)

dcp(REPO / "scripts" / "repair_links.py", "/tmp/")
dcp(REGISTRY, "/tmp/")
dcp(IMPORT_MAP, "/tmp/")
r = subprocess.run(C[:-2] + ["/opt/omero/server/venv3/bin/python", "/tmp/repair_links.py",
                             creds["OMERO_ROOT_PASS"]],
                   capture_output=True, text=True)
print(r.stdout.strip() or r.stderr[-500:], flush=True)
if r.returncode != 0:
    raise SystemExit("repair_links failed")

# personal 'All <user> data' projects: created as the user, delta-maintained
dcp(REPO / "scripts" / "personal_projects.py", "/tmp/")
r = subprocess.run(C[:-2] + ["/opt/omero/server/venv3/bin/python", "/tmp/personal_projects.py",
                             creds["OMERO_ROOT_PASS"]],
                   capture_output=True, text=True)
print(r.stdout.strip() or r.stderr[-500:], flush=True)
if r.returncode != 0:
    raise SystemExit("personal_projects failed")
