#!/usr/bin/env bash
# Stage 2 of the gjesus3 -> OMERO sync: import whatever the mirror delivered
# that OMERO doesn't have yet, then annotate the new images.
# Run inside WSL:  bash run_pipeline.sh
# (Stage 1 is sync_gjesus3.ps1 on the Windows side.)
set -eu
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$REPO/scripts/import_all.py"
bash "$REPO/scripts/run_annotation.sh"
