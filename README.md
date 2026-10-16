# VolleyVision

**Computer vision-based player detection and tracking for volleyball match footage.**

## Goal

Develop a reproducible machine learning pipeline that identifies volleyball players in recorded matches, tracks them across frames, and visualizes their movement.

## Initial scope

- Player detection using a pretrained object detection model
- Multi-object tracking with persistent IDs
- Annotated video export
- Quantitative evaluation of detection and tracking quality

## Planned extensions

- Court calibration
- Player movement trails and heatmaps
- Fine-tuning on volleyball-specific footage
- Interactive match analysis interface

## Technology

Python, PyTorch, Ultralytics YOLO, OpenCV, ByteTrack

## Development approach

This project prioritizes understanding the underlying computer vision algorithms, reproducible experiments, and honest evaluation over feature count.

## Status

**Planning and foundational study.** Model results have not yet been established.

## Limitations

Initial support targets recorded matches with a fixed camera and a clear view of the court. Tracking IDs may change after occlusions. The first version will not identify players by name or recognize volleyball actions.
