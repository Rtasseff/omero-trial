# Stage 1 of the gjesus3 -> OMERO sync: mirror new acquisitions and snapshot
# the registries. Windows-side because J:\ is a Windows drive mapping.
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\rtasseff\projects\miniProjects\202608_omero-trial\scripts\sync_gjesus3.ps1
# Stage 2 (import + annotate) is run_pipeline.sh in WSL.
#
# NOT scheduled anywhere yet — deliberate; see the daily-refresh discussion in
# gjesus3-tools 06_omero_trial_runbook.md.
$src = 'J:\gjesus3-data\raw\MICROSCOPY'
$dst = 'D:\projects\gjesus3-tools\omero-trial\data\MICROSCOPY'
$man = 'D:\projects\gjesus3-tools\omero-trial\manifest'

robocopy $src $dst /E /R:2 /W:5 /MT:8 /NP /NFL /NDL /LOG:"$man\robocopy_sync.log"
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy reported failures (exit $LASTEXITCODE); see $man\robocopy_sync.log"
    exit 1
}
Copy-Item 'J:\gjesus3-data\registries\registry_raw.csv',
          'J:\gjesus3-data\registries\registry_projects.csv' $man
Write-Output "sync stage 1 done (robocopy exit $LASTEXITCODE); now run stage 2 in WSL: bash run_pipeline.sh"
