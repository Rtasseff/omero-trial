#!/usr/bin/env bash
# Foreground annotation run with its own log; detach at the Windows level:
#   powershell: Start-Process -WindowStyle Hidden wsl.exe -ArgumentList `
#     '-d','Ubuntu','--','bash','/home/rtasseff/projects/miniProjects/202608_omero-trial/scripts/annotate_load.sh'
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG=/mnt/d/projects/gjesus3-tools/omero-trial/manifest/annotate_initial.log
{
  echo "annotate start $(date -Is)"
  bash "$REPO/scripts/run_annotation.sh"
  echo "annotate exit $? $(date -Is)"
} > "$LOG" 2>&1
