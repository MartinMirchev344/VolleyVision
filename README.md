# VolleyVision

Computer vision for volleyball player detection, tracking, and movement heatmaps from recorded matches.

## Showcase scope

Build a reproducible local ABLE Mentor demonstration that:

- Detects visible players with a pretrained detector.
- Tracks players with temporary anonymous IDs.
- Exports annotated video and per-frame tracking data in CSV or JSON.
- Generates movement heatmaps after the detection and tracking baseline works.
- Documents measured results, failure cases, and limitations.

Player recognition means detecting players, without identifying names or jersey numbers. Start with a permitted local MP4 from a fixed camera, preferably elevated behind the end line.

## Preferred technology

Python, PyTorch, OpenCV, an Ultralytics YOLO-family detector, ByteTrack, NumPy, and pandas, with a minimal CLI and pytest where appropriate. Verify model selection, dependency versions, GPU compatibility, and licensing before integration.

## Status and development

Week 1 project documentation only. No runnable pipeline, environment setup, or measured model results exist yet.

Proceed one approved milestone at a time. Discuss how each component works, why it is chosen, its limitations, and presentation questions in chat before implementation. Keep personal learning records out of the repository.

## Documentation

- [Project specification](VOLLEYVISION.md)
- [Problem definition](docs/problem.md)
- [Local data handling](data/README.md)

## Limitations and exclusions

IDs may change after occlusion or re-entry. Initial support excludes moving cameras and camera cuts. Image-coordinate heatmaps show observed positions in the camera view; top-down court heatmaps require validated calibration. Neither alone establishes running distances or tactical conclusions.

Ball tracking, action recognition, named player identification, cloud deployment, and a full web application are outside the showcase scope. Fine-tuning is a later option if baseline evaluation justifies it.
