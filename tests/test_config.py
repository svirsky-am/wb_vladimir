import pytest

from wb_sync.app_config import AppConfig


def test_token_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    cfg = AppConfig(work_dir=tmp_path)
    assert cfg.api_token == "tok"


def test_token_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        AppConfig(work_dir=tmp_path)


def test_fetch_data_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("FETCH_DATA", "0")
    cfg = AppConfig(work_dir=tmp_path)
    assert cfg.fetch_data is False


def test_interval_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    with pytest.raises(ValueError):
        AppConfig(work_dir=tmp_path, fetch_interval_minutes=0)


def test_database_and_log_in_work_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    cfg = AppConfig(work_dir=tmp_path)
    assert cfg.database_file == tmp_path / "wb_sync.db"
    assert cfg.log_file == tmp_path / "wb_sync.log"
