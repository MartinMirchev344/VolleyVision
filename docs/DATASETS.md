# Dataset and checkpoint register

Audit date: 21 October 2026. No third-party dataset, footage, or model checkpoint has
been downloaded or used. Status remains **pending** until source/version evidence is
sufficient; an advertised license alone is not a provenance audit.

## Reference repository

- https://github.com/shukkkur/VolleyVision
- README advertises CC BY-NC-ND 4.0; `LICENSE.md` contains GNU AGPL-3.0.
- Evidence: README blob `b39acbb12823ea6b6cf7aeb2b212dc158ff1ac4e`;
  LICENSE.md blob `6bb5339778ba01632d750030cba42b79b48181fa`.
- Decision: do not copy code or weights under unresolved conflicting terms. A dataset
  license must be checked at its own source; the repository license does not resolve it.

## Ball candidate

- Project: https://universe.roboflow.com/shukur-sabzaliev1/volleyball_v2
- Inspected version: https://universe.roboflow.com/shukur-sabzaliev1/volleyball_v2/dataset/3
- Advertised license: CC BY 4.0; class `volleyball`; 18,980 version images;
  stretch preprocessing to 1024×768; advertised 80/10/10 split.
- Provenance: description says multiple Universe datasets plus manual annotations;
  constituent source permissions and recording IDs are not yet established.
- Decision: pending; no training/inference checkpoint clearance implied. Prefer
  auditing original-resolution v1 for tiny-ball training, before selecting an export.
- Attribution if cleared: project author Shukur Sabzaliev1/Shakhansho Sabzaliev,
  exact version URL, CC BY 4.0 link, modifications, and required constituent credits.

## Player candidate

- Specification URL: https://universe.roboflow.com/shukur-sabzaliev-42xvj/players-dataset
  was not accessible through the research tool.
- Matching candidate: https://universe.roboflow.com/actions-players/players-dataset
  advertises CC BY 4.0, `ball` and `player`, and a cloned source. Its overview lists
  206 images while its displayed trained version references 344; distinguish project
  images from processed version images when auditing an export.
- Decision: pending identity/version/provenance confirmation. A pretrained person
  detector is the initial baseline, so this dataset is not required in Week 1.

## Action candidate

- Specification URL: https://universe.roboflow.com/shukur-sabzaliev-42xvj/volleyball-actions
  was not accessible through the research tool.
- Matching candidate: https://universe.roboflow.com/actions-players/volleyball-actions
- Inspected version: https://universe.roboflow.com/actions-players/volleyball-actions/dataset/5
- Advertised CC BY 4.0; v5 original has 13,923 images and reports 13 class remappings.
  The project overview lists 15 source labels and several contributing datasets.
- Decision: pending confirmation of project continuity, constituent rights, actual
  export class names and mapping to `serve`, `set`, `spike`, `block`, `defense`.
  Do not infer that `passing`, `digging`, or actor labels are semantically interchangeable.

## Code and weights

Ultralytics: https://www.ultralytics.com/license advertises AGPL-3.0 and Enterprise
terms and addresses trained models/proprietary deployment. No checkpoint, exact
runtime version, or commercial usage decision is selected. Ultralytics is not part
of the core installation. The baseline adapter is available for a later cleared,
trusted local `.pt` checkpoint; no automatic model download is allowed.

CC BY 4.0 permits commercial adaptation with attribution under its terms:
https://creativecommons.org/licenses/by/4.0/. This does not establish the uploader's
rights to every source frame, nor resolve privacy/publicity or weight/code rights.
Record educational processing, training, redistribution and potential commercial
use separately. Request source-owner clarification if evidence is ambiguous.

## Private footage and evidence

Keep actual permission evidence, names, inventory, annotation exports and source
hashes in ignored `data/` files. No private recording is currently supplied. Use
existing owner-authorized recordings if external sources cannot be cleared; no
unlicensed video downloads and no requirement to record new footage.

For every approved asset record URL, exact version, download/export date, SHA256,
license text/evidence, owner, source recordings, attribution, allowed operations,
publication restrictions, decision/reviewer, and split methodology. Hashes are
unavailable until an authorized download; do not invent them.

Build train/validation/test splits by independent match/recording session and check
duplicates across splits. Do not accept advertised percentages as evidence of
independence. If source grouping cannot be reconstructed, do not claim a clean
generalization benchmark. Keep the local test recording out of training/tuning.
