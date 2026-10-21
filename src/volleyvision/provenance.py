"""Explicit local permission records; public URLs alone are not permission."""

import json
from pathlib import Path

from volleyvision.video import file_sha256


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Manifest must be a JSON object.")
    return value


def require_video_permission(video: Path, record_path: Path) -> dict:
    record = load_json(record_path)
    required = ("recording_id", "permission_evidence", "owner", "allowed_uses")
    if any(not isinstance(record.get(key), str) or not record[key].strip() for key in required):
        raise ValueError("Permission record needs recording_id, owner, evidence, and allowed uses.")
    if record.get("processing_permitted") is not True:
        raise ValueError("Footage processing permission has not been established.")
    if record.get("sha256") != file_sha256(video):
        raise ValueError("Footage SHA256 does not match its permission record.")
    if record.get("split") not in ("development", "validation", "test"):
        raise ValueError("Permission record needs a development, validation, or test split.")
    return record


def require_model_permission(manifest_path: Path, task: str) -> tuple[dict, Path]:
    record = load_json(manifest_path)
    if record.get("usage_decision") != "permitted" or record.get("inference_permitted") is not True:
        raise ValueError("Model code and checkpoint inference permissions must be established.")
    required = ("model_id", "source_url", "code_license_url", "weights_license_url", "reviewed_by")
    if any(not isinstance(record.get(key), str) or not record[key].strip() for key in required):
        raise ValueError(
            "Model manifest needs identity, source, code/weight licenses, and reviewer."
        )
    if record.get("task") != task:
        raise ValueError("Model manifest task does not match the requested baseline.")
    if task == "ball" and record.get("volleyball_specific") is not True:
        raise ValueError("Ball baseline requires a volleyball-specific checkpoint.")
    key = record.get("checkpoint")
    if not isinstance(key, str) or not key:
        raise ValueError("Model manifest needs an existing local checkpoint path.")
    checkpoint = (manifest_path.parent / key).resolve()
    if not checkpoint.is_file() or checkpoint.suffix.lower() != ".pt":
        raise ValueError("Supply a trusted local .pt checkpoint; automatic downloads are disabled.")
    if record.get("sha256") != file_sha256(checkpoint):
        raise ValueError("Checkpoint SHA256 does not match its manifest.")
    mapping = record.get("class_map")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Model manifest needs an explicit source-label to canonical class_map.")
    allowed = {
        "players": {"player"},
        "ball": {"volleyball"},
        "actions": {"serve", "set", "spike", "block", "defense"},
    }[task]
    if any(not isinstance(k, str) or not k for k in mapping) or set(mapping.values()) != allowed:
        raise ValueError(f"Class map must cover exactly these canonical labels: {sorted(allowed)}")
    return record, checkpoint
