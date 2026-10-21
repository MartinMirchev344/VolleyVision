# Local data

Store private recordings, extracted frames, annotations, and a video inventory locally under this directory. The root `.gitignore` excludes its contents except Markdown documentation. Do not put sensitive details in Markdown files here because they can be tracked.

Store generated videos, tracking exports, and heatmaps in the ignored `outputs/` directory. Common recording formats and model weights are also ignored.

## Inventory convention

When footage is available, maintain a private, ignored CSV such as `data/video-inventory.csv` with:

- Local filename or path and match/recording identifier.
- Source, owner, permission evidence, allowed uses, and publication restrictions.
- Resolution, frame rate, duration, and candidate clip timestamps.
- Camera angle and motion, court visibility, lighting, and occlusion notes.
- Suitability for the fixed-camera demonstration.

No recordings or inventory are supplied. Public availability alone does not establish permission to use or redistribute footage.

## Private permission and model manifests

Calibration and inference require `--permission-record data/permission.json`. After
inspecting the video hash, create an ignored JSON record with `recording_id`,
`sha256`, `owner`, `permission_evidence`, `allowed_uses`, `split` (`development`,
`validation`, or `test`), and `processing_permitted: true` only when established.
Keep the evidence and publication/training/retention restrictions alongside it.

Inference additionally requires `--model-manifest data/player-model.json` (or ball/
actions). Record `model_id`, `task` (`players`, `ball`, or `actions`), `source_url`,
`code_license_url`, `weights_license_url`, `reviewed_by`, `checkpoint` (local `.pt`
path relative to the manifest), `sha256`, `usage_decision`, `inference_permitted`,
and `class_map`. Leave the decision pending and permission false until reviewed.
For players map the checkpoint's person/player source label to `player`; for ball
map its volleyball label to `volleyball` and require `volleyball_specific: true`.
For actions explicitly map verified label meanings to all five canonical classes:
`serve`, `set`, `spike`, `block`, `defense`. Do not guess ambiguous class semantics.

These records document a human decision; they cannot establish legal rights by
themselves. Never load an untrusted `.pt` file. No model manifest or weight is supplied.

Generated court calibration JSON belongs here too. Local PostgreSQL cluster files,
logs and its initialization password file are also ignored; they are infrastructure,
not evaluation footage. Do not include any private information in tracked Markdown.
