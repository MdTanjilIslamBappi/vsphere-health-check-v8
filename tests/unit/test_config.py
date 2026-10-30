import pytest

from vhealth.config import load_config
from vhealth.ingestion.exceptions import VHealthError


def test_load_config_defaults_log_window_weeks_to_thirteen():
    config = load_config(None)
    assert config.log_window_weeks == 13


def test_load_config_reads_log_window_weeks_from_toml(tmp_path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text("[assessment]\nlog_window_weeks = 4\n", encoding="utf-8")
    config = load_config(config_path)
    assert config.log_window_weeks == 4


def test_load_config_rejects_log_window_weeks_above_twenty_six(tmp_path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text("[assessment]\nlog_window_weeks = 27\n", encoding="utf-8")
    with pytest.raises(VHealthError):
        load_config(config_path)


def test_load_config_rejects_log_window_weeks_below_one(tmp_path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text("[assessment]\nlog_window_weeks = 0\n", encoding="utf-8")
    with pytest.raises(VHealthError):
        load_config(config_path)
