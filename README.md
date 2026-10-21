# VolleyVision

Offline volleyball video analysis for a small ABLE Mentor showcase. The target is a
permitted, fixed-camera rally with court-aware anonymous player tracks, a
volleyball-specific ball detector, candidate action events, and human-reviewed
scoring. Raw footage and generated video stay in local storage; PostgreSQL stores
metadata, predictions, and reviews.

## Current milestone

Week 1 provides video inspection, normalized manual polygon calibration,
permission-checked independent detector trials, environment diagnostics, and a
PostgreSQL/Alembic bootstrap. This is not yet the integrated showcase pipeline.
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
.\.venv\Scripts\python.exe -m volleyvision --help
.\.venv\Scripts\python.exe -m volleyvision doctor
.\.venv\Scripts\python.exe -m volleyvision inspect --input data/rally.mp4
```

Inspection prints the content hash needed for a private footage permission record.
Calibration and inference require that record. Detector inference also requires a
trusted local checkpoint and an explicitly reviewed model manifest; see
[data and manifest conventions](data/README.md). The core installation does not
install Ultralytics or fetch weights.

```powershell
.\.venv\Scripts\python.exe -m volleyvision calibrate --input data/rally.mp4 --permission-record data/permission.json --output data/court-v1.json --author reviewer
.\.venv\Scripts\python.exe -m volleyvision baseline --input data/rally.mp4 --permission-record data/permission.json --model-manifest data/player-model.json --task players --calibration data/court-v1.json --start-sec 0 --end-sec 10 --track --device 0 --output outputs/player-trial-01
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
quality. [Experiment results and remaining blockers](reports/experiments.md).

## Project documents

- [Specification and milestones](VOLLEYVISION.md)
- [Problem definition](docs/problem.md)
- [Dataset and checkpoint decisions](docs/DATASETS.md)
- [Evaluation protocol](docs/evaluation-plan.md)
- [Database and storage design](docs/database.md)
- [Engineering decisions](docs/decisions.md)
- [Dependency licensing inventory](docs/dependencies.md)

Anonymous track IDs can switch after occlusion or re-entry. Calibration does not
make footpoints exact or identify a person as a player. Candidate actions are not
successful actions or confirmed points. Camera cuts/movement require recalibration.
No public app, live processing, jersey recognition, automatic scoring, or metric
movement claims are part of this milestone.
