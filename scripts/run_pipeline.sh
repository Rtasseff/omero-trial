#!/usr/bin/env bash
# Stage 2 of the gjesus3 -> OMERO sync: import whatever the mirror delivered
# that OMERO doesn't have yet, then annotate the new images.
# Run inside WSL:  bash run_pipeline.sh
# (Stage 1 is sync_gjesus3.ps1 on the Windows side.)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# import_all exits 1 when any acquisition failed (e.g. the known Bio-Formats
# CZI bug, see manifest/import_failures.csv) -- that must not block the later
# stages for the acquisitions that DID import. Run all, report the worst exit.
python3 "$REPO/scripts/import_all.py"; imp=$?
bash "$REPO/scripts/run_annotation.sh"; ann=$?
python3 "$REPO/scripts/assign_ownership.py"; own=$?
if [ "$ann" -ne 0 ]; then exit "$ann"; fi
if [ "$own" -ne 0 ]; then exit "$own"; fi
exit "$imp"
