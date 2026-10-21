import pytest

from volleyvision.cli import main
from volleyvision.db import database_url


def test_missing_input_has_clear_nonzero_exit(tmp_path, capsys):
    assert main(["inspect", "--input", str(tmp_path / "missing.mp4")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_database_url_is_explicit_and_errors_do_not_echo_credentials(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="Set DATABASE_URL"):
        database_url()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///secret-password")
    with pytest.raises(ValueError, match="postgresql") as exc:
        database_url()
    assert "secret-password" not in str(exc.value)


def test_database_driver_exception_is_redacted(monkeypatch, capsys):
    def fail():
        raise RuntimeError("postgresql://user:secret-password@server/db")

    monkeypatch.setattr("volleyvision.db.check_database", fail)
    assert main(["db-check"]) == 1
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "secret-password" not in error
