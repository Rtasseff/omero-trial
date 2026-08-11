#!/usr/bin/env bash
# Create the trial group + accounts on the OMERO server (idempotent-ish: rerun
# errors on existing objects are reported but harmless). Ran 2026-08-10.
# Run inside WSL:  bash setup_accounts.sh
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO/.env"
source "$REPO/accounts.env"
OMERO="docker exec omero-trial_omeroserver_1 /opt/omero/server/venv3/bin/omero"
ROOT="-s localhost -u root -w $OMERO_ROOT_PASS"

# read-annotate: students can view everything and add comments/tags,
# but cannot edit or delete the imported originals.
# 2026-08-11: trial1/trial2 renamed live to jesus/itziar (omero obj update
# Experimenter:N omeName=...), marta added. This bootstrap now recreates
# the current three-user set on a fresh server.
$OMERO $ROOT group add gjesus3-trial --type=read-annotate
$OMERO $ROOT user add "$OMERO_IMPORTER_USER" GJesus3 Importer --group-name gjesus3-trial -P "$OMERO_IMPORTER_PASS"
$OMERO $ROOT user add "$OMERO_TRIAL1_USER" Jesus Ruiz-Cabello --group-name gjesus3-trial -P "$OMERO_TRIAL1_PASS"
$OMERO $ROOT user add "$OMERO_TRIAL2_USER" Itziar Trial --group-name gjesus3-trial -P "$OMERO_TRIAL2_PASS"
$OMERO $ROOT user add "$OMERO_TRIAL3_USER" Marta Trial --group-name gjesus3-trial -P "$OMERO_TRIAL3_PASS"
$OMERO $ROOT group info gjesus3-trial
