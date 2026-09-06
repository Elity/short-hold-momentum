import pytest

from shm.source import source_revision


def test_source_revision_uses_env_when_repo_has_no_git(tmp_path, monkeypatch) -> None:
    revision = "a" * 40
    monkeypatch.setenv("SHM_SOURCE_REVISION", revision)

    assert source_revision(tmp_path) == revision


def test_source_revision_rejects_invalid_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SHM_SOURCE_REVISION", "not-a-full-sha")

    with pytest.raises(RuntimeError, match="40-character hexadecimal SHA"):
        source_revision(tmp_path)
