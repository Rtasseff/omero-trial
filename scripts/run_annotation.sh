#!/usr/bin/env bash
# Attach gjesus3 metadata to imported images (see annotate_all.py).
# Run inside WSL:  bash run_annotation.sh [--refresh]
set -eu
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME=/mnt/d/projects/gjesus3-tools/omero-trial
source "$REPO/accounts.env"
C=omero-trial_omeroserver_1
docker cp "$REPO/scripts/annotate_all.py" "$C:/tmp/"
docker cp "$DATA_HOME/manifest/registry_raw.csv" "$C:/tmp/"
docker cp "$DATA_HOME/manifest/import_map.csv" "$C:/tmp/"
docker exec "$C" /opt/omero/server/venv3/bin/python /tmp/annotate_all.py \
    "$OMERO_IMPORTER_USER" "$OMERO_IMPORTER_PASS" "$@"
