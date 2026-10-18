# Problem definition

## Intended use

VolleyVision will help a volleyball coach or analyst review where visible players move during an existing match recording. The initial deliverable is a local ABLE Mentor demonstration of player detection, anonymous tracking, and movement heatmaps.

## Supported footage

Use a permitted local MP4. Start with a fixed, preferably elevated camera behind the end line; elevated sideline footage is also acceptable. Select a clip with clear court visibility and no camera cuts or significant camera movement.

## Planned deliverables

1. Detect visible players with a pretrained detector.
2. Associate detections across frames using temporary anonymous IDs.
3. Export video with player boxes and IDs, plus per-frame CSV or JSON tracking data.
4. Generate movement heatmaps after the detection and tracking baseline works.
5. Provide reproducible local execution and an evidence-backed evaluation or failure analysis.

Heatmaps are part of the showcase scope. Choose their coordinate system and sampling method before implementation. Image-coordinate maps describe observed positions in the camera view. Top-down court maps require calibration and validation of the projection. Document the effects of perspective, occlusion, and identity switches; do not infer precise distances or performance from an unvalidated map.

## Exclusions

- Identification by name or jersey number.
- Ball tracking, action classification, or tactical recommendations.
- Guaranteed identity continuity through occlusion, re-entry, or camera cuts.
- Real-time guarantees, hosting, accounts, payments, or a full web interface.
- Fine-tuning unless evaluation establishes a need.

## Validation

Evaluate on permitted, representative footage. Record configuration and clip characteristics alongside measured results. Similar uniforms, referees, spectators, partial visibility, and occlusion can cause detection errors and identity switches. Do not claim unmeasured accuracy or runtime.

## Current milestone

Week 1 defines scope and data conventions. Environment setup and video inspection tooling belong to Week 2. Detection, tracking, and heatmaps follow in separate approved steps. Footage suitability, hardware compatibility, and model performance have not been verified.
