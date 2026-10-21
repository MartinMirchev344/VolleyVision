# PostgreSQL and artifact storage

Use PostgreSQL with synchronous SQLAlchemy 2.x, psycopg 3 and Alembic. The bootstrap
revision establishes migration history only; no feature tables exist yet. Database
credentials come from environment variables. No SQLite fallback is used to stand
in for PostgreSQL tests.

## First feature migration (Weeks 2–3)

| Entity | Proposed contents and constraints |
|---|---|
| videos | UUID PK; optional future match reference; filename, storage key, SHA256, byte size, positive FPS/width/height, nonnegative frame count/duration; UTC creation time |
| court_calibrations | UUID PK; video FK; normalized court/playable polygons and tolerance, source frame and dimensions, mode/version/author; unique video+version; immutable versions |
| processing_runs | UUID PK; video and calibration references; model IDs/hashes, configuration snapshot, status, UTC start/end, hardware/performance and error details |
| player_tracks | UUID PK; run FK; anonymous integer track ID; first/last frame, eligibility; unique run+track_id; optional human roster mapping later |
| player_observations | track FK, original frame/time, bbox, confidence and eligibility status; indexed track+frame |

Use normalized relations and UUID durable IDs, run-scoped track integers, named
constraints, bbox/time/confidence checks, and explicit deletion policy. JSONB is
appropriate for immutable configurations and polygon coordinate arrays, not a
substitute for all entity relations. Validate geometry in application code as well.

Later feature migrations introduce matches, ball observations, separate action frame
predictions and aggregated action events, manual rallies, players/match rosters,
scoring review history, and artifacts. Add run/frame/time/event-status indexes when
the corresponding queries exist. Make run persistence transactional and failures
visible; reruns receive new IDs and do not overwrite reviews.

Predictions and reviews remain independent. Count confirmed accepted scoring
decisions using a current-review view or versioned decisions, preserving earlier
decisions for audit and preventing correction duplicates. Do not maintain mutable
point counters independently of the reviewed records.

## Filesystem boundary

Raw/annotated videos live in ignored local folders by default. Store a storage key,
content hash, size and metadata in PostgreSQL; no raw MP4 bytea or frame-image blobs.
`VOLLEYVISION_STORAGE_ROOT` will be consumed by ingestion when that feature arrives;
Week 1 commands instead take explicit local input/output paths.

At ingestion, introduce a minimal `StorageBackend` with read/write/existence/delete
operations and a local implementation. Resolve relative keys inside its configured
root and reject path traversal. Object storage can implement the same boundary later;
do not add S3 or MinIO now. Keep source artifacts immutable and register successful
output artifacts only after closing the file and computing its checksum.

Database deletion must not silently orphan or destroy video files. Initially reject
deleting referenced records until an explicit retention/deletion workflow exists.
Define the later review/roster retention policy before cascading these entities.

## Time, privacy, and tests

Record creation uses UTC timezone-aware timestamps. Events and observations use
original video indices/relative times. Raw PostgreSQL data, secrets, and private
footage stay out of Git. Public output requires appropriate publication permission,
especially where faces/minors are visible. Keep retention/deletion evidence private.

Integration tests require `TEST_DATABASE_URL` pointing to a disposable test database;
they use an isolated temporary schema to check upgrade/downgrade, repeat upgrade,
and persistence after reconnect. A restart check is a separate infrastructure smoke
test. Feature foreign keys, duplicate observations, review corrections and artifact
deletion will be tested when those migrations/features arrive.
