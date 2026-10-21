# VolleyVision project specification

Architecture approved 21 October 2026. Work in small, reviewable milestones within
4–6 hours of human effort per week. Final research and architecture decisions belong
to the developer. Explain each major component and its validation before extending it.

## Target showcase

Process a lawfully obtained fixed-camera MP4 and produce an annotated short rally,
machine-readable exports, and an honest analysis report with:

1. YOLO person/player detections filtered by manually calibrated court/playable
   geometry, with ByteTrack anonymous local IDs and visible uncertainty.
2. A volleyball-specific fine-tuned YOLO ball detector; motion association, bounded
   short-gap prediction, reacquisition, and visibly distinct observed/predicted trails.
3. A YOLO action detector for `serve`, `set`, `spike`, `block`, and `defense`.
   Aggregate frame evidence per track and class into time-bounded candidate events.
4. Manual rally boundaries, an event timeline, candidate/reviewed counts kept
   separate, and human-confirmed attack kills, service aces, and block points.
5. PostgreSQL persistence for metadata, run-versioned predictions, roster mappings,
   and independent human reviews. Store video files locally behind a small storage
   interface; keep paths/object keys and hashes in the database.

No fully automatic referee-quality scoring, jersey OCR, guaranteed whole-match
identities, real-time streaming, moving-camera support, multi-camera synchronization,
or public application platform. Heatmaps/homography are later optional features;
image-plane footpoints do not establish distances or tactical conclusions. TrackNet
is excluded from the MVP.

## Initial engineering choices

- Python 3.11, OpenCV, NumPy, PyTorch and a supported YOLO implementation; test before
  pinning exact versions/checkpoints. Target hardware: RTX 5070, 12 GB.
- Detect people first, then apply calibrated geometry. Use normalized court and
  playable polygons, footpoints, configurable boundary tolerance and uncertain status.
- Track candidate people and filter eligibility for output initially. Add short
  eligibility hysteresis in the integrated player milestone; measure the trade-off
  against pre-tracking filtering.
- Ball association starts with motion gating and a Kalman baseline; stop predictions
  across long gaps and reset/reacquire after large residuals.
- Action attribution uses spatial/temporal evidence; ambiguous actors remain null.
  Different tracks can have simultaneous spike/block events. Keep frame predictions
  separate from events; tune support, merging and cooldown on validation data.
- argparse CLI, synchronous SQLAlchemy 2.x, psycopg 3, Alembic, local PostgreSQL,
  pytest, and JSON/CSV exports. No paid service is required for the core tools.

## Rights and reproducibility

Record exact dataset/checkpoint versions, source provenance, licenses, attribution,
and permitted educational/commercial uses before downloading or using them. Public
visibility is insufficient. Review code, weights, labels and source footage separately;
unclear rights block their use. Do not copy the reference project's implementation.
Keep credentials, private permissions, recordings, extracted frames, labels, and
weights outside Git. Do not select a public project license implicitly.

Split data by match/recording session, never adjacent random frames. Keep the test
recording out of tuning/training. Preserve source frame indices and video-relative
times; use UTC for record creation. Record actual hardware, versions, thresholds,
latency and memory. Never claim unmeasured results or identify tracks as real players.

Human scoring decisions support unknown/rejected/corrected/confirmed outcomes with
an audit trail. Only confirmed accepted attribution contributes to player points;
corrections must not double-count. These points are not automatically all team points.

## Milestones

| Weeks | Deliverable |
|---|---|
| 1 | Rights/environment audit, small calibration and independent baseline tools, held-out annotation protocol, PostgreSQL bootstrap/schema design |
| 2–3 | Court-aware player pipeline, ByteTrack, eligibility hysteresis, output and first feature migrations |
| 4–5 | Licensed volleyball ball fine-tuning/evaluation, motion association and gap-aware trails |
| 6–8 | Licensed five-class action model and per-track temporal event detection |
| 9–10 | Conservative actor association, manual rally timeline and SQL-backed analytics |
| 11 | Local human review and scoring correction with audit/no-double-count tests |
| 12 | Held-out validation, reproducible demonstration and published limitations |

Week 1 is complete only when permissions, a real rally and annotations, available
licensed model trials, environment verification, and database checks are evidenced.
Missing footage or model rights must be reported as blockers. Do not fake a complete
pipeline or add future feature tables before their milestone. If data/model access
fails, keep the smaller valid deliverable and revise the schedule explicitly.

Future boundaries permit an HTTP API, workers, object storage, authentication and
frontend later. They are not dependencies of the offline prototype.
