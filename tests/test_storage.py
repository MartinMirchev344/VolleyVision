import pytest

from volleyanalytics.storage import LocalStorage, validate_key


@pytest.mark.parametrize(
    "key",
    [
        "",
        " match.mp4",
        "../escape.mp4",
        "a/../../b.mp4",
        "/abs.mp4",
        "C:/x.mp4",
        "a\\b.mp4",
        "./a",
        "a//b.mp4",
        "a/",
    ],
)
def test_unsafe_keys_are_rejected(key):
    with pytest.raises(ValueError):
        validate_key(key)


def test_key_for_file_inside_root_and_read_back(tmp_path):
    root = tmp_path / "matches"
    (root / "match-01").mkdir(parents=True)
    video = root / "match-01" / "match-01.mp4"
    video.write_bytes(b"fixture bytes")
    storage = LocalStorage(root)
    key = storage.key_for(video)
    assert key == "match-01/match-01.mp4"
    assert storage.exists(key)
    assert storage.size(key) == len(b"fixture bytes")
    with storage.open_read(key) as stream:
        assert stream.read() == b"fixture bytes"
    assert not storage.exists("match-01/missing.mp4")


def test_files_outside_root_and_missing_roots_are_rejected(tmp_path):
    root = tmp_path / "matches"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    storage = LocalStorage(root)
    with pytest.raises(ValueError, match="inside the storage root"):
        storage.key_for(outside)
    with pytest.raises(ValueError, match="does not exist"):
        storage.key_for(root / "missing.mp4")
    with pytest.raises(ValueError, match="does not exist"):
        LocalStorage(tmp_path / "no-such-root")


def test_storage_root_must_be_configured(monkeypatch):
    monkeypatch.delenv("VOLLEYANALYTICS_STORAGE_ROOT", raising=False)
    with pytest.raises(ValueError, match="VOLLEYANALYTICS_STORAGE_ROOT"):
        LocalStorage.from_environment()
