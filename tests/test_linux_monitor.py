"""Pytests for linux_monitor.py"""

import pytest
import yaml

CONFIG_FILE = "linux_monitor/linux_monitor_config.yml"
from linux_monitor.linux_monitor import SystemMetrics

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

@pytest.mark.cpu_metrics
def test_get_cpu_metrics():
    """Test get_cpu_metrics()"""
    system_metrics.get_cpu_metrics()
    assert system_metrics.metrics["system_cpu"]["system.cpu.user"]
    assert system_metrics.metrics["system_cpu"]["system.cpu.system"]
    assert system_metrics.metrics["system_cpu"]["system.cpu.idle"]
    assert system_metrics.metrics["system_cpu"]["system.cpu.iowait"]

@pytest.mark.metrics
def test_get_mem_metrics():
    """Test get_mem_metrics()"""
    system_metrics.get_mem_metrics()
    assert system_metrics.metrics["system_mem"]["system.mem.total"]
    assert system_metrics.metrics["system_mem"]["system.mem.available"]

@pytest.mark.swap_metrics
def test_get_swap_metrics():
    """Test get_swap_metrics()"""
    system_metrics.get_swap_metrics()
    assert system_metrics.metrics["swap_memory"]["system.swap.free"]
    assert system_metrics.metrics["swap_memory"]["system.swap.used"]
