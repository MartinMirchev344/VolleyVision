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