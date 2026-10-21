"""Tests for config parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexus_router.config import BusyConfig, ConfigError, EstimateConfig, load_config, parse_config

ROOT = Path(__file__).resolve().parent.parent


def node(name="a", **extra):
    return {"name": name, "ollama_url": f"http://{name}:11434", **extra}


def test_defaults():
    cfg = parse_config({"nodes": [node()]})
    assert (cfg.host, cfg.port) == ("0.0.0.0", 11434)
    assert cfg.poll_interval_s == 2.0
    assert cfg.stale_after_s == 10.0
    assert cfg.agent_token is None
    assert cfg.estimate == EstimateConfig(overhead_factor=1.2, overhead_mb=512)
    assert cfg.busy == BusyConfig(gpu_util_percent=85, consecutive_polls=3)
    n = cfg.nodes[0]
    assert (n.agent_url, n.priority, n.reserve_mb) == (None, 100, 512)


def test_stale_after_scales_with_poll_interval():
    assert parse_config({"nodes": [node()], "poll_interval_s": 5}).stale_after_s == 25.0
    assert parse_config({"nodes": [node()], "poll_interval_s": 5, "stale_after_s": 7}).stale_after_s == 7.0


def test_busy_check_can_be_disabled():
    cfg = parse_config({"nodes": [node()], "busy": {"gpu_util_percent": None}})
    assert cfg.busy.gpu_util_percent is None


def test_example_config_loads():
    cfg = load_config(ROOT / "config.example.yaml")
    assert [n.name for n in cfg.nodes] == ["rtx4080", "rtx2070"]
    assert cfg.port == 11434
    assert cfg.poll_interval_s == 2
    assert cfg.stale_after_s == 10.0
    assert cfg.estimate == EstimateConfig()
    assert cfg.busy == BusyConfig()
    assert cfg.nodes[0].reserve_mb == 1024


def test_empty_file_is_a_config_error(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("")
    with pytest.raises(ConfigError, match="nodes"):
        load_config(path)


@pytest.mark.parametrize("raw", [None, [], "nodes", {}, {"nodes": []}, {"nodes": None}])
def test_missing_nodes(raw):
    with pytest.raises(ConfigError):
        parse_config(raw)


@pytest.mark.parametrize("bad", [{"ollama_url": "http://x"}, {"name": "x"}, "x"])
def test_node_needs_name_and_ollama_url(bad):
    with pytest.raises(ConfigError, match=r"nodes\[0\].*name.*ollama_url"):
        parse_config({"nodes": [bad]})


def test_error_names_the_offending_node_index():
    with pytest.raises(ConfigError, match=r"nodes\[1\]"):
        parse_config({"nodes": [node("a"), {"name": "b"}]})


def test_duplicate_node_names():
    with pytest.raises(ConfigError, match="duplicate node name 'a'"):
        parse_config({"nodes": [node("a"), node("a")]})


def test_trailing_slashes_stripped():
    cfg = parse_config(
        {"nodes": [{"name": "a", "ollama_url": "http://h:11434/", "agent_url": "http://h:11500//"}]}
    )
    assert cfg.nodes[0].ollama_url == "http://h:11434"
    assert cfg.nodes[0].agent_url == "http://h:11500"


def test_priority_defaults_to_file_order():
    cfg = parse_config({"nodes": [node("a"), node("b"), node("c")]})
    assert [n.priority for n in cfg.nodes] == [100, 101, 102]
    assert [n.name for n in cfg.nodes_by_priority] == ["a", "b", "c"]


def test_explicit_priority_overrides_file_order():
    cfg = parse_config({"nodes": [node("a", priority=5), node("b", priority=1), node("c")]})
    assert [n.name for n in cfg.nodes_by_priority] == ["b", "a", "c"]
