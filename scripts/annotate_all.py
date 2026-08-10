"""Attach gjesus3 metadata to every imported image as OMERO key-value pairs.

Two map-annotation blocks per image, both in the client namespace (visible and
searchable in OMERO.web):

  1. registry block — the acquisition's registry row (cohort-level fields)
     plus `gjesus3_path`, the researcher-usable UNC location
     (\\\\gjesus3\\gjesus3\\gjesus3-data\\raw\\...).
  2. sidecar block — metadata.json flattened to dot-path keys, whitelisted to:
     top-level scalars, the user_supplied / discovered / subject / condition /
     anatomy blocks (all sublevels), and microscopy minus microscopy._raw_metadata.

Modes:
  default    annotate only images that have no importer-owned client-ns block yet
             (the cheap daily mode)
  --refresh  delete the importer's existing client-ns blocks and rewrite them
             (schema changes; never touches other users' annotations)

Runs INSIDE the omero-server container (see run_annotation.sh):
  .../python /tmp/annotate_all.py <user> <pass> [--refresh]
Needs /tmp/registry_raw.csv and /tmp/import_map.csv (docker cp'd in) and the
sidecars at /gjesus3-data/... (the compose bind).
"""
import csv
import json
import re
import sys

import omero
from omero.gateway import BlitzGateway
from omero.constants.metadata import NSCLIENTMAPANNOTATION

UNC_ROOT = r"\\gjesus3\gjesus3\gjesus3-data"
REGISTRY_FIELDS = [
    "acq_id", "project_id", "instrument", "instrument_model",
    "acquisition_datetime", "researcher", "operator", "sample_id",
    "sample_type", "sample_organism", "subject_ids", "anatomical_entity",
    "session_id", "original_name", "file_format", "notes",
]
SIDECAR_BLOCKS = ["user_supplied", "discovered", "subject", "condition", "anatomy"]
MAX_VAL = 500

def flatten(obj, prefix=""):
    """dict -> dot-path pairs; lists of scalars join, lists of dicts index;
    empty values dropped."""
    pairs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            pairs += flatten(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        if obj and all(not isinstance(x, (dict, list)) for x in obj):
            val = "; ".join(str(x) for x in obj if x not in ("", None))
            if val:
                pairs.append((prefix.rstrip("."), val))
        else:
            for i, x in enumerate(obj):
                pairs += flatten(x, f"{prefix.rstrip('.')}.{i}.")
    else:
        if obj not in ("", None):
            pairs.append((prefix.rstrip("."), str(obj)[:MAX_VAL]))
    return pairs

def sidecar_pairs(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{type(e).__name__}: {e}"
    pairs = []
    for k, v in d.items():
        if not isinstance(v, (dict, list)) and v not in ("", None):   # top-level scalars
            pairs.append((k, str(v)[:MAX_VAL]))
    for block in SIDECAR_BLOCKS:
        if block in d:
            pairs += flatten(d[block], block + ".")
    if isinstance(d.get("microscopy"), dict):
        m = {k: v for k, v in d["microscopy"].items() if k != "_raw_metadata"}
        pairs += flatten(m, "microscopy.")
    return pairs, None

def main():
    user, pw = sys.argv[1], sys.argv[2]
    refresh = "--refresh" in sys.argv[3:]
    conn = BlitzGateway(user, pw, host="localhost", port=4064)
    if not conn.connect():
        raise SystemExit("connect failed")
    conn.c.enableKeepAlive(60)
    my_id = conn.getUser().getId()

    reg = {r["acq_id"]: r
           for r in csv.DictReader(open("/tmp/registry_raw.csv", newline="", encoding="utf-8"))}
    work = [r for r in csv.DictReader(open("/tmp/import_map.csv", newline="", encoding="utf-8"))
            if r["image_ids"] != "FAILED"]

    n_img = n_skip = n_err = 0
    for idx, row in enumerate(work, 1):
        r = reg.get(row["acq_id"])
        if r is None:
            print(f"no registry row for {row['acq_id']}", flush=True)
            n_err += 1
            continue
        rel = r["canonical_path"].lstrip("/")[len("raw/"):]      # MICROSCOPY/.../ACQ-x/
        reg_pairs = [[k, r[k][:MAX_VAL]] for k in REGISTRY_FIELDS if r.get(k)]
        reg_pairs.append(["gjesus3_path",
                          UNC_ROOT + r["canonical_path"].replace("/", "\\")])
        sc_pairs, sc_err = sidecar_pairs(f"/gjesus3-data/{rel}metadata.json")
        if sc_err:
            print(f"sidecar problem {row['acq_id']}: {sc_err}", flush=True)

        for img_id in re.split(r"[;,]", row["image_ids"]):
            img = conn.getObject("Image", int(img_id))
            if img is None:
                print(f"missing image {img_id} ({row['acq_id']})", flush=True)
                n_err += 1
                continue
            mine = [a for a in img.listAnnotations()
                    if isinstance(a, omero.gateway.MapAnnotationWrapper)
                    and a.getNs() == NSCLIENTMAPANNOTATION
                    and a.getDetails().getOwner().getId() == my_id]
            if mine and not refresh:
                n_skip += 1
                continue
            if mine:
                conn.deleteObjects("MapAnnotation", [a.getId() for a in mine], wait=True)
            for pairs in (reg_pairs, sc_pairs or []):
                if not pairs:
                    continue
                ann = omero.gateway.MapAnnotationWrapper(conn)
                ann.setNs(NSCLIENTMAPANNOTATION)
                ann.setValue([[str(k), str(v)] for k, v in pairs])
                ann.save()
                img.linkAnnotation(ann)
            n_img += 1
        if idx % 100 == 0:
            print(f"[{idx}/{len(work)}] {n_img} annotated, {n_skip} already current",
                  flush=True)

    print(f"annotate_all done: {n_img} images annotated, {n_skip} skipped, "
          f"{n_err} problems", flush=True)
    conn.close()

if __name__ == "__main__":
    main()
