"""Video file storage boundary. PostgreSQL stores keys and hashes, never video bytes."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

STORAGE_ROOT_VARIABLE = "VOLLEYANALYTICS_STORAGE_ROOT"


def validate_key(key: str) -> str:
    """Accept only relative POSIX keys that cannot escape the storage root."""
    if not isinstance(key, str) or not key or key != key.strip():
        raise ValueError("Storage key must be a non-empty string without surrounding spaces.")
    if "\\" in key or ":" in key or "\x00" in key:
        raise ValueError("Storage key must use forward slashes and no drive or special characters.")
    # Split the raw string: path normalisation would silently hide "./a" or "a//b".
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError("Storage key must be relative with no empty, '.' or '..' parts.")
    return key


class StorageBackend(ABC):
    """Minimal operations shared by local disk now and object storage later."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def open_read(self, key: str) -> BinaryIO: ...

    @abstractmethod
    def size(self, key: str) -> int: ...


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        if not root.is_dir():
            raise ValueError(f"Storage root does not exist or is not a directory: {root}")
        self.root = root.resolve()

    @classmethod
    def from_environment(cls) -> "LocalStorage":
        value = os.environ.get(STORAGE_ROOT_VARIABLE, "")
        if not value:
            raise ValueError(f"Set {STORAGE_ROOT_VARIABLE} to the local video folder.")
        return cls(Path(value))

    def path(self, key: str) -> Path:
        resolved = (self.root / validate_key(key)).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("Storage key resolves outside the storage root.")
        return resolved

    def key_for(self, path: Path) -> str:
        """Key of a file already inside the root, so large videos are registered in place."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"Video must be inside the storage root ({self.root}); move it there.")
        if not resolved.is_file():
            raise ValueError(f"Video file does not exist: {path}")
        return validate_key(resolved.relative_to(self.root).as_posix())

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def open_read(self, key: str) -> BinaryIO:
        return self.path(key).open("rb")

    def size(self, key: str) -> int:
        return self.path(key).stat().st_size
