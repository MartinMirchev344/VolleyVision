# VolleyAnalytics

Offline volleyball video analysis for a small ABLE Mentor showcase. The target is a
permitted, fixed-camera rally with court-aware anonymous player tracks, a
volleyball-specific ball detector, candidate action events, and human-reviewed
scoring. Raw footage and generated video stay in local storage; PostgreSQL stores
metadata, predictions, and reviews.

## Current milestone

Week 1 provides video inspection, normalized manual polygon calibration,
permission-checked independent detector trials, environment diagnostics, PostgreSQL
with Alembic migrations, source-video registration, and the match statistics
database. This is not yet the integrated showcase pipeline.
No real footage, model weights, training results, or volleyball accuracy measurements
are included. Ball motion tracking, temporal action events, and scoring review arrive
in later milestones.

## Quick start

Use Python 3.11 and a local virtual environment. See [setup](docs/setup.md) for the
tested environment, optional CUDA packages, and database commands.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m volleyanalytics --help
.\.venv\Scripts\python.exe -m volleyanalytics doctor
.\.venv\Scripts\python.exe -m volleyanalytics inspect --input data/matches/match-01/match-01.mp4
```

Keep each match recording under `data/matches/<match>/` (ignored by Git). With
`DATABASE_URL` and `VOLLEYANALYTICS_STORAGE_ROOT` set (see [setup](docs/setup.md))
and migrations applied, register it in PostgreSQL without copying the file:

```powershell
.\.venv\Scripts\python.exe -m volleyanalytics import-video --file data/matches/match-01/match-01.mp4
```

Match statistics live in PostgreSQL as rallies and graded touches; the box score
(per-player points, serve, reception, attack and block, team totals, set scores and
partials) is computed from them on request. Figures from unreviewed AI records are
labelled as estimates. See [database design](docs/database.md#statistics).

```powershell
.\.venv\Scripts\python.exe -m volleyanalytics stats --match-id <match-uuid>
.\.venv\Scripts\python.exe -m volleyanalytics stats --match-id <match-uuid> --reviewed-only --format json
```

Model quality is measured on frames from the match labelled by a person. `label-export`
prepares frames pre-filled with model boxes and `label-studio` starts a local labelling
tool; see [labelling](docs/setup.md#labelling-label-studio).

`evaluate` scores a player or ball model against labelled frames: a Label Studio export
or a YOLO-format dataset such as a VolleyVision export. Players match by box overlap
(IoU ≥ 0.5) and the ball by centre distance. The JSON report gives precision, recall,
AP50, player recall by box height (far-court players are small), and the frames with
the most errors; `--calibration` adds a second score with the court filter applied.

```powershell
.\.venv\Scripts\python.exe -m volleyanalytics evaluate --labels data/labeling/test-01/export.json --model-manifest data/models/upstream-players/model.json --task players --calibration <court.json> --device 0 --output outputs/eval/players-upstream.json
```

Inspection prints the content hash needed for a private footage permission record.
Calibration and inference require that record. Detector inference also requires a
trusted local checkpoint and an explicitly reviewed model manifest; see
[data and manifest conventions](data/README.md). The core installation does not
install Ultralytics or fetch weights; the detector runtime is pinned separately in
`requirements-models.txt` (see [setup](docs/setup.md)).

```powershell
.\.venv\Scripts\python.exe -m volleyanalytics calibrate --input data/matches/match-01/match-01.mp4 --permission-record data/matches/match-01/permission.json --output data/matches/match-01/court-v1.json --author reviewer
.\.venv\Scripts\python.exe -m volleyanalytics baseline --input data/matches/match-01/match-01.mp4 --permission-record data/matches/match-01/permission.json --model-manifest data/models/players/model.json --task players --calibration data/matches/match-01/court-v1.json --config configs/players.yaml --start-sec 0 --end-sec 10 --track --device 0 --output outputs/player-trial-01
```

Each baseline run writes an annotated MP4, detection CSV/JSONL, a frame ledger
(including frames with no detections), and run metadata. Source indices and times
are preserved in exports. The MP4 uses nominal FPS; it is a visual preview, not a
replacement for the source timestamps on variable-rate video. Excluded detections
remain in exports; uncertain boundary detections stay visible in yellow.

## Checks

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs/test-tmp
.\.venv\Scripts\ruff.exe check src tests migrations
.\.venv\Scripts\ruff.exe format --check src tests migrations
```

Database integration checks run only with `TEST_DATABASE_URL` set to a dedicated
test database. Tests create synthetic video; they do not measure volleyball model
quality.

## Project documents

- [Specification and milestones](VOLLEYANALYTICS.md)
- [Problem definition](docs/problem.md)
- [Evaluation protocol](docs/evaluation-plan.md)
- [Database and storage design](docs/database.md)
- [Dependency licensing inventory](docs/dependencies.md)

## Credits

Volleyball datasets and reference code by Shukur Sabzaliev
([shukkkur/VolleyVision](https://github.com/shukkkur/VolleyVision)), used with the
author's permission. Datasets published on Roboflow Universe under CC BY 4.0.

Anonymous track IDs can switch after occlusion or re-entry. Calibration does not
make footpoints exact or identify a person as a player. Candidate actions are not
successful actions or confirmed points. Camera cuts/movement require recalibration.
No public app, live processing, jersey recognition, automatic scoring, or metric
movement claims are part of this milestone.
