from pathlib import Path

import pytest
import yaml

from volleyanalytics.baseline import _tracker_config

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def test_builtin_tracker_is_default(tmp_path):
    assert _tracker_config({}, tmp_path / "run.yaml") == ("bytetrack.yaml", None)
    assert _tracker_config({"tracker": "botsort.yaml"}, tmp_path / "run.yaml")[0] == "botsort.yaml"


def test_tracker_file_resolves_next_to_config_and_is_recorded():
    config = yaml.safe_load((CONFIGS / "players.yaml").read_text(encoding="utf-8"))
    path, settings = _tracker_config(config, CONFIGS / "players.yaml")
    assert Path(path) == (CONFIGS / "bytetrack-volleyball.yaml").resolve()
    assert settings["tracker_type"] == "bytetrack" and settings["track_buffer"] == 90


@pytest.mark.parametrize(
    ("name", "content"),
    [("missing.yaml", None), ("bad.yaml", "tracker_type: deepsort\n"), ("bad.txt", "x: 1\n")],
)
def test_invalid_tracker_files_are_rejected(tmp_path, name, content):
    if content is not None:
        (tmp_path / name).write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="tracker"):
        _tracker_config({"tracker": name}, tmp_path / "run.yaml")
