#!/usr/bin/env bash
# One-shot initial bulk load: import everything the mirror holds, then
# annotate. Runs in the FOREGROUND and logs to manifest/pipeline_initial.log --
# detachment happens at the Windows level (a hidden persistent wsl.exe):
#   powershell: Start-Process -WindowStyle Hidden wsl.exe -ArgumentList `
#     '-d','Ubuntu','--','bash','/home/rtasseff/projects/miniProjects/202608_omero-trial/scripts/initial_load.sh'
# (WSL tears down setsid/nohup process groups when the launching session
# exits, so in-WSL detachment does not survive; a live wsl.exe does.)
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG=/mnt/d/projects/gjesus3-tools/omero-trial/manifest/pipeline_initial.log
{
  echo "pipeline start $(date -Is)"
  bash "$REPO/scripts/run_pipeline.sh"
  echo "pipeline exit $? $(date -Is)"
} > "$LOG" 2>&1
