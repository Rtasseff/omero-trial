# omero-trial — OMERO pilot serving gjesus3 microscopy data

A ~1-month researcher pilot: OMERO on the Data Office workstation serving the
full gjesus3 `raw\MICROSCOPY` archive (read-only mirror) to the hardwired
network, so students can browse/search their own data in a real image-server UI.
**Arm A** of the bake-off in `gjesus3-tools/04_omero_xnat_spike_plan.md`; the
operating runbook and go/no-go scoreboard live in
`gjesus3-tools/06_omero_trial_runbook.md`. This repo is the code + config.

## Layout of the whole system

| Piece | Where | Why there |
|---|---|---|
| Code + compose + secrets | this repo (WSL, backed up; secrets `.env`/`accounts.env` git-ignored) | source lives in git, WSL is backed up |
| Data mirror (~424 GB) | `D:\projects\gjesus3-tools\omero-trial\data\` | cache of `J:\gjesus3-data\raw\MICROSCOPY` — regenerable, allowed on unbacked D: |
| Working state (import map, registry snapshots, robocopy logs) | `D:\...\omero-trial\manifest\` | regenerable artifacts |
| PostgreSQL + OMERO managed repo (symlinks + caches) | docker named volumes `omero-trial_database` / `omero-trial_omero` (WSL disk) | **user annotations live here — pilot-grade only, students are informed** |
| Port-forward 0.0.0.0:4080 → WSL | WorkstationOps op instance (fallback: `scripts/start_forward.ps1`) | all listeners managed in one place |

## Everyday commands

```bash
# status / start / stop (in WSL, from this directory)
docker-compose ps
docker-compose up -d
docker-compose stop

# end-to-end health check (login + thumbnail + pixel render)
bash scripts/smoke_web.sh http://10.10.2.195:4080
```

## The sync pipeline (gjesus3 → OMERO)

1. **Stage 1 — Windows** (`J:\` only exists there): `scripts/sync_gjesus3.ps1`
   robocopy-mirrors new acquisitions to D:\ and snapshots the registries.
2. **Stage 2 — WSL**: `bash scripts/run_pipeline.sh` imports anything new
   in-place (`ln_s`, no data duplication) and annotates it.

Both stages are idempotent and delta-aware; run them manually for now
(deliberately unscheduled — see the runbook's daily-refresh discussion).

## Metadata on every image (OMERO key-value pairs)

- **registry block**: the acquisition's `registry_raw.csv` row + `gjesus3_path`
  (UNC form `\\gjesus3\gjesus3\gjesus3-data\raw\...` researchers can paste).
- **sidecar block**: `metadata.json` flattened to dot-path keys, whitelisted to
  top-level scalars, `user_supplied`, `discovered`, `subject`, `condition`,
  `anatomy`, and `microscopy` minus `microscopy._raw_metadata`.

Schema changes: rerun `bash scripts/run_annotation.sh --refresh` (rewrites only
the importer's blocks; never touches annotations students added).

## History

Started 2026-08-10 as a 31-acquisition subset at `D:\image-server\omero-trial`;
same-day rescoped to the full microscopy archive and rehomed (code → this repo,
data → `D:\projects\gjesus3-tools\omero-trial`). First-iteration scripts in
`scripts/attic/`.
