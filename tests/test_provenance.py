import json

import pytest

from volleyvision.provenance import require_model_permission, require_video_permission
from volleyvision.video import file_sha256


def test_footage_requires_permission_and_matching_content(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"test fixture; not footage")
    record = {
        "recording_id": "fixture",
        "owner": "test",
        "permission_evidence": "fixture",
        "allowed_uses": "tests",
        "split": "test",
        "processing_permitted": False,
        "sha256": file_sha256(video),
    }
    path = tmp_path / "permission.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="permission"):
        require_video_permission(video, path)
    record["processing_permitted"] = True
    path.write_text(json.dumps(record))
    assert require_video_permission(video, path)["split"] == "test"
    video.write_bytes(b"different source")
    with pytest.raises(ValueError, match="SHA256"):
        require_video_permission(video, path)


def test_checkpoint_gate_and_class_semantics(tmp_path):
    weights = tmp_path / "fixture.pt"
    weights.write_bytes(b"not executable model weights")
    record = {
        "usage_decision": "pending",
        "inference_permitted": True,
        "model_id": "test",
        "source_url": "https://example.org/source",
        "code_license_url": "https://example.org/code-license",
        "weights_license_url": "https://example.org/weights-license",
        "reviewed_by": "test",
        "task": "ball",
        "checkpoint": "fixture.pt",
        "sha256": file_sha256(weights),
        "class_map": {"ball": "volleyball"},
        "volleyball_specific": False,
    }
    path = tmp_path / "manifest.json"

    def save():
        path.write_text(json.dumps(record))

    save()
    with pytest.raises(ValueError, match="permissions"):
        require_model_permission(path, "ball")
    record["usage_decision"] = "permitted"
    save()
    with pytest.raises(ValueError, match="volleyball-specific"):
        require_model_permission(path, "ball")
    record["volleyball_specific"] = True
    save()
    assert require_model_permission(path, "ball")[1] == weights
    record["task"] = "actions"
    save()
    with pytest.raises(ValueError, match="canonical labels"):
        require_model_permission(path, "actions")
    weights.unlink()
    with pytest.raises(ValueError, match="automatic downloads"):
        require_model_permission(path, "actions")
