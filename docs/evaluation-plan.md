# First-rally evaluation

## Dataset selection and labeling

Choose a permitted 8–15 second fixed-camera rally. Record the source SHA256,
recording/session ID, permission evidence, camera angle, resolution, nominal FPS,
manual rally bounds, and split in ignored `data/` files. Development and test must
use different recording sessions; different clips of the same match are not an
independent split. If only one recording is available, call results descriptive.

Freeze thresholds and model versions before the test trial. Camera calibration can
use the reference image; do not use test detection labels to tune margins. During
Week 1 label about 12 representative frames with player boxes and active/off-court/
uncertain eligibility. Label one roughly two-second consecutive segment with stable
ground-truth IDs and visible ball centers. Label action intervals and actor identity
where clear throughout the rally. Record absent action classes as unevaluated.

Annotation exports stay private. Use source-pixel xyxy boxes, source frame indices,
video-relative seconds and anonymous ground-truth actor IDs. Mark truncated/occluded
players, unobservable ball positions, ambiguous actors, and annotation uncertainty.
Do not interpolate ground truth through invisible ball intervals. Document whether
`defense` means dig/reception and do not silently remap generic passes.

## Measurements

- Players: one-to-one IoU matching (initial reporting threshold 0.5), precision and
  recall with counts; compare detector-only and court-filtered results on identical
  labels. Report off-court false inclusions and active-player false exclusions,
  separating model misses from filtering errors. Include net/baseline/free-zone cases.
- Tracking: ID switches and fragmentation on consecutive labeled frames. IDF1/HOTA
  require compatible dense annotations/evaluation tooling; sparse frames are insufficient.
- Ball: precision/recall on observable labels, center error in source pixels, missed
  visible frames, longest miss streak and reacquisition delay. Predeclare a distance
  threshold using ball size on development footage and freeze it before testing;
  report the threshold and ball-size distribution. Later compare detector-only vs
  motion tracking, separating observed and predicted samples.
- Actions: frame-level box/class metrics separately from event precision/recall/F1.
  For later temporal events use one-to-one class matching with a declared tolerance
  (initial proposal ±0.5 seconds around labeled onset, validation-tuned). Report
  duplicate events, per-class support, actor correctness and unknown-attribution rate.
- Scoring later: compare confirmed reviews to manual outcomes; test that unverified
  candidates contribute zero and corrections never count twice.
- Runtime: record cold-start and processing scope, configuration, package versions,
  checkpoint hash, GPU, FPS, resolution and peak allocated VRAM. No real-time claim
  without measurement. The current runner includes decode/inference/render/export
  in processing time; model loading is outside that timer.

## Week 1 gates

1. Rights decisions are explicit and tied to exact assets; unresolved assets are unused.
2. Environment imports and CUDA tensor computation pass; actual detector inference is
   separately pending until a cleared checkpoint exists.
3. Calibration saves/loads, scales at equal aspect ratio, rejects invalid polygons,
   and distinguishes eligible/uncertain/excluded footpoints. Manual click interaction
   must also be tried on the actual permitted recording.
4. The first real rally has documented annotations and baseline evidence, or is
   explicitly blocked. A synthetic video test does not satisfy this gate.
5. PostgreSQL connection, migration roundtrip and persistence are verified separately.
6. Report failure cases and sample denominators; do not claim reliable five-class
   event performance from one rally.

No arbitrary accuracy pass mark is justified before clip inspection. Use Week 1
errors to propose validation targets for the next milestone. Geometry and export
correctness have deterministic tests; model quality needs labeled real footage.
