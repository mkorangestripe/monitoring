"""Pytests for linux_monitor.py"""

import pytest
import yaml

from linux_monitor import CONFIG_FILE
from linux_monitor import SystemMetrics

system_metrics = SystemMetrics()

@pytest.mark.config_file
def test_open_config_file():
    """Test open_config_file()"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as yaml_in_file:
        assert yaml.safe_load(yaml_in_file)

@pytest.mark.metrics
def test_get_load_avg():
    """Test get_load_avg()"""
    system_metrics.get_load_avg()
    assert system_metrics.metrics["system_load_avg"]["system.load.1"]
    assert system_metrics.metrics["system_load_avg"]["system.load.5"]
    assert system_metrics.metrics["system_load_avg"]["system.load.15"]

@pytest.mark.metrics
def test_get_uptime():
    """Test get_uptime()"""
    system_metrics.get_uptime()
    assert system_metrics.metrics["system.uptime"]
