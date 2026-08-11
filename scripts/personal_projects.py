"""Maintain per-user personal projects: 'All <username> data'.

Ryan's decision 2026-08-12: since the owner filter shows only owned top-level
containers, every researcher gets one auto-maintained project owned by them,
holding LINKS to every image they own (images stay in their acquisition
projects too - multi-linking, nothing moves). One dataset 'all' inside.

Created for the group's human accounts (not root/guest/importer - the
importer's pile is the unclaimed shared tree). Shells are created AS the user
(admin sudo), so no chown is involved and nothing gets severed. Contents are
delta-maintained: links added for newly owned images, links removed if an
image's owner changes. Runs INSIDE the omero-server container after the link
repair (assign_ownership.py invokes it):
  .../python /tmp/personal_projects.py <root-pass>
"""
import sys

import omero
from omero.gateway import BlitzGateway
from omero.model import DatasetImageLinkI, DatasetI, ImageI, ProjectDatasetLinkI, ProjectI
from omero.rtypes import rstring, rlong
from omero.sys import ParametersI

BATCH = 500
SKIP = {"root", "guest", "gjesus3"}

conn = BlitzGateway("root", sys.argv[1], host="localhost", port=4064)
if not conn.connect():
    raise SystemExit("connect failed")
group = conn.getObject("ExperimenterGroup", attributes={"name": "gjesus3-trial"})
gid = group.getId()
conn.SERVICE_OPTS.setOmeroGroup(gid)
q = conn.getQueryService()
opts = conn.SERVICE_OPTS

leaders, colleagues = group.groupSummary()
members = [(u.getId(), u.getOmeName()) for u in leaders + colleagues
           if u.getOmeName() not in SKIP]

update = conn.getUpdateService()
for uid, login in sorted(members, key=lambda m: m[1]):
    pname = f"All {login} data"

    p = ParametersI(); p.add("n", rstring(pname)); p.add("o", rlong(uid))
    rows = q.projection(
        "select l.parent.id, l.child.id from ProjectDatasetLink l "
        "where l.parent.name = :n and l.parent.details.owner.id = :o", p, opts)
    if rows:
        pid_, did = rows[0][0].val, rows[0][1].val
    else:
        uc = conn.suConn(login)          # create AS the user: shells natively theirs
        try:
            uc.SERVICE_OPTS.setOmeroGroup(gid)
            pr = ProjectI(); pr.setName(rstring(pname))
            ds = DatasetI(); ds.setName(rstring("all"))
            pdl = ProjectDatasetLinkI(); pdl.setParent(pr); pdl.setChild(ds)
            saved = uc.getUpdateService().saveAndReturnObject(pdl, uc.SERVICE_OPTS)
            pid_, did = saved.parent.id.val, saved.child.id.val
        finally:
            uc.close()

    p2 = ParametersI(); p2.add("o", rlong(uid))
    owned = {r[0].val for r in q.projection(
        "select i.id from Image i where i.details.owner.id = :o", p2, opts)}
    p3 = ParametersI(); p3.add("d", rlong(did))
    linked = {}          # image id -> (link id, image owner id)
    for r in q.projection(
            "select l.id, l.child.id, l.child.details.owner.id "
            "from DatasetImageLink l where l.parent.id = :d", p3, opts):
        linked[r[1].val] = (r[0].val, r[2].val)

    add = sorted(owned - set(linked))
    stale = [link_id for img, (link_id, owner) in linked.items()
             if owner != uid or img not in owned]
    links = []
    for iid in add:
        link = DatasetImageLinkI()
        link.setParent(DatasetI(did, False))
        link.setChild(ImageI(iid, False))
        links.append(link)
    for i in range(0, len(links), BATCH):
        update.saveArray(links[i:i + BATCH], opts)
    if stale:
        conn.deleteObjects("DatasetImageLink", stale, wait=True)
    print(f"{login}: '{pname}' (Project:{pid_}) +{len(add)} -{len(stale)} "
          f"= {len(owned)} images", flush=True)

conn.close()
