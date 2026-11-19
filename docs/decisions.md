# Engineering decisions

## 19 November 2026 — project renamed to VolleyAnalytics

- The project, Python package (`volleyanalytics`), CLI and storage variable
  (`VOLLEYANALYTICS_STORAGE_ROOT`) are renamed from VolleyVision. This removes
  confusion with the upstream reference project `shukkkur/VolleyVision`, whose
  datasets are audited separately in `DATASETS.md`; references to it keep its name.
- The specification file is renamed to `VOLLEYANALYTICS.md`.
- The upstream author granted permission to use the project and its datasets; dataset
  decisions in `DATASETS.md` are updated accordingly.
- The existing portable PostgreSQL databases keep their `volleyvision` names. They hold
  only the bootstrap migration, so renaming them would add risk without benefit.
- Renaming the GitHub repository and the local checkout folder is left to the developer.

## 21 October 2026 — feasibility foundations

- The showcase scope includes players, volleyball ball, action events, human scoring
  review and PostgreSQL. Earlier player/heatmap-only scope is superseded. Heatmaps
  and homography are optional later work.
- Keep Week 1 limited to environment, rights audit, calibration, independent detector
  trials, evaluation preparation and database bootstrap. No training or full app.
- Use Python 3.11 and argparse. The CLI is small enough that an additional command
  framework provides little benefit. Use a local virtual environment and pin the
  installed core dependencies after tests.
- Use OpenCV signed polygon distance on bbox footpoints. The tolerance is a fraction
  of the shorter source-image side, so it scales with resolution. Boundary points
  are uncertain; no geometric confidence probability is fabricated.
- Default to an explicitly selected court-plus-free-zone polygon. Strict court is
  available. Manual polygons are image geometry, not measured world coordinates.
- Run ByteTrack on candidate people, explicitly selecting its configuration. Export
  excluded people for audit while suppressing them in the rendered layer. Integrated
  eligibility hysteresis is deferred to the player milestone.
- Run-versioned JSONL/CSV is available without database connectivity. PostgreSQL
  persistence is a later feature integration, not an implicit success on DB failure.
- Choose synchronous SQLAlchemy 2.x + psycopg 3. An async stack adds complexity to an
  offline batch tool without a demonstrated requirement. Initialize Alembic history
  without prematurely creating the full conceptual schema.
- Keep core tools independent of Ultralytics. Runtime/code and checkpoint rights are
  separate unresolved decisions. No model is silently downloaded or selected.
- Do not automatically count serve/spike/block detections as points, identify tracker
  IDs as roster identities, or combine frame predictions into events globally.
- Preserve private inventory and permission evidence in ignored files; project docs
  contain public provenance questions rather than private names or recording details.

## Questions for the next review

1. Which existing recording is permitted for processing and publication, and is a
   separate recording available for development?
2. Can the dataset owner establish constituent footage rights and original recording
   grouping? Which code/checkpoint licensing route fits eventual distribution?
3. How much ball detail survives at the chosen input resolution, and which action
   classes are observable from the target camera? Decide from measured trials.
