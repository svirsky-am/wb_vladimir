import pytest

from wb_sync.app_config import AppConfig


def test_token_from_env(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    cfg = AppConfig(work_dir="wd_cfg1")
    assert cfg.api_token == "tok"


def test_token_missing_raises(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        AppConfig(work_dir="wd_cfg2")


def test_fetch_data_env_override(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.delenv("FETCH_DATA", raising=False)
    assert AppConfig(work_dir="wd_cfg3").fetch_data is True
    monkeypatch.setenv("FETCH_DATA", "0")
    assert AppConfig(work_dir="wd_cfg3b").fetch_data is False


def test_interval_validation(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("FETCH_INTERVAL_MINUTES", "-5")
    with pytest.raises(ValueError):
        AppConfig(work_dir="wd_cfg4")


def test_database_and_log_in_work_dir(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    cfg = AppConfig(work_dir="wd_cfg5")
    assert cfg.database_path.parent == cfg.work_dir
    assert cfg.responses_dir == cfg.work_dir / "responses"
    assert (cfg.work_dir / "wb_sync.log").exists()


def test_sandbox_flag(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("WB_SANDBOX", "1")
    assert AppConfig(work_dir="wd_cfg6").sandbox is True
