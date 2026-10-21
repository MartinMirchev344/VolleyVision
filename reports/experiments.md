# Feasibility checks — 21 October 2026

## Verified environment

- Windows x64, Python 3.11.17 in a project-local virtual environment.
- Core package versions: `requirements-lock.txt`; optional GPU environment:
  `requirements-cuda.txt`. Dependency terms: `docs/dependencies.md`.
- NVIDIA RTX 5070; driver 617.42; reported GPU memory 12,227 MiB.
- PyTorch 2.11.0+cu128, torchvision 0.26.0+cu128, CUDA build 12.8.
- `python -m volleyvision doctor`: CUDA available; device capability 12.0;
  GPU allocation/matrix multiplication/synchronization passed. This is not detector
  inference or a volleyball performance benchmark.

## Engineering checks

- Ruff formatting/static checks pass.
- pytest: **23 passed**, including PostgreSQL integration when `TEST_DATABASE_URL`
  was set. Without that variable the database test is explicitly skipped.
- Synthetic MJPG video checks: metadata, frame indices, bounded timestamps,
  reference-frame access, invalid input and unavailable-PTS fallback.
- Court geometry checks: footpoint rather than box center, boundary tolerance,
  free-zone eligibility, normalized roundtrip/scaling, aspect-ratio changes and
  invalid polygons. Actual click interaction on permitted footage remains untested.
- Provenance checks: permission refusal, content mismatch, local-weight-only policy,
  volleyball-specific requirement and action class-map coverage.
- PostgreSQL **17.11** portable local instance: connection passed; Alembic bootstrap
  upgrade/downgrade/re-upgrade and repeat upgrade passed in an isolated test schema.
  Migration head survived reconnect and an actual server restart. Server stopped
  after verification; see `docs/setup.md` to start it. No Windows service installed.
- Docker Compose execution was not tested because Docker is not installed.

## Remaining feasibility blockers

No permitted recording, rally annotations, approved model checkpoint, or cleared
Ultralytics runtime/checkpoint combination is supplied. No third-party footage,
dataset or model weights were downloaded. Independent detector adapters therefore
have not been exercised with a real model. No detection/tracking/action accuracy,
event/scoring results, inference FPS or training outcomes are claimed.

Week 1 foundations are implemented; the real-rally/model evaluation gate is pending.
Next input: an owner-authorized fixed-camera recording with permission evidence and
independent development footage, plus explicit code/weight license decisions.
