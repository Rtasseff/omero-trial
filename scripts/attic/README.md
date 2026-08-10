# attic — first-iteration scripts, retired

`select_subset.py` + `copy_subset.py` built the original 31-acquisition trial
subset (2026-08-10, same day). Superseded the same day by the decision to load
**all** of `raw\MICROSCOPY`: the robocopy mirror (`sync_gjesus3.ps1`) replaced
selection+copy, and `import_all.py` replaced the manifest-driven importer.
Kept for reference; they still run but write to paths that no longer exist.
