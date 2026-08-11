"""Re-link orphaned images into their acquisition's (project, instrument)
dataset, as root.

WHY THIS EXISTS: omero chown implements "give the image away" as "remove it
from the giver's containers" - it deletes the giver-owned DatasetImageLinks,
and in a read-annotate group the new owner cannot link into the importer's
dataset themselves. Admin-created links are OMERO's sanctioned mechanism for
mixed-owner trees: root may link any image into any dataset, and root-owned
links are not the giver's, so later chowns leave them alone. Run after every
ownership pass (assign_ownership.py invokes this).

Runs INSIDE the omero-server container (docker cp'd with the two CSVs):
  .../python /tmp/repair_links.py <root-pass>
"""
import csv
import sys

import omero
from omero.gateway import BlitzGateway
from omero.model import DatasetImageLinkI, DatasetI, ImageI

BATCH = 500

conn = BlitzGateway("root", sys.argv[1], host="localhost", port=4064)
if not conn.connect():
    raise SystemExit("connect failed")
group = conn.getObject("ExperimenterGroup", attributes={"name": "gjesus3-trial"})
gid = group.getId()
conn.SERVICE_OPTS.setOmeroGroup(gid)

reg = {r["acq_id"]: r for r in csv.DictReader(open("/tmp/registry_raw.csv", newline="", encoding="utf-8"))}
img2acq = {}
for row in csv.DictReader(open("/tmp/import_map.csv", newline="", encoding="utf-8")):
    if row["image_ids"] == "FAILED":
        continue
    for part in row["image_ids"].split(";"):
        for i in part.split(","):
            img2acq[int(i)] = row["acq_id"]

q = conn.getQueryService()
opts = conn.SERVICE_OPTS

# (project_id prefix, dataset name) -> dataset id
ds_map = {}
for r in q.projection(
        "select p.name, d.id, d.name from Project p "
        "join p.datasetLinks pl join pl.child d", None, opts):
    pname, did, dname = r[0].val, r[1].val, r[2].val
    ds_map[(pname.split(" · ")[0], dname)] = did

orphans = [r[0].val for r in q.projection(
    "select i.id from Image i where not exists "
    "(select l from DatasetImageLink l where l.child = i)", None, opts)]

links, skipped = [], 0
for iid in orphans:
    acq = img2acq.get(iid)
    r = reg.get(acq) if acq else None
    if r is None:
        skipped += 1
        continue
    key = (r["project_id"] or "PROJ-none", r["instrument"])
    did = ds_map.get(key)
    if did is None:
        print(f"no dataset for {key} (image {iid})", flush=True)
        skipped += 1
        continue
    link = DatasetImageLinkI()
    link.setParent(DatasetI(did, False))
    link.setChild(ImageI(iid, False))
    links.append(link)

update = conn.getUpdateService()
for i in range(0, len(links), BATCH):
    update.saveArray(links[i:i + BATCH], opts)
print(f"relinked {len(links)} images ({skipped} skipped) of {len(orphans)} orphans", flush=True)
conn.close()
