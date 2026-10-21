"""Router configuration loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class NodeConfig:
    name: str
    ollama_url: str
    agent_url: str | None = None
    priority: int = 100
    reserve_mb: int = 512


@dataclass(frozen=True)
class EstimateConfig:
    overhead_factor: float = 1.2
    overhead_mb: int = 512


@dataclass(frozen=True)
class BusyConfig:
    # None disables utilization-based busy detection.
    gpu_util_percent: int | None = 85
    consecutive_polls: int = 3


@dataclass(frozen=True)
class Config:
    nodes: list[NodeConfig]
    host: str = "0.0.0.0"
    port: int = 11434
    poll_interval_s: float = 2.0
    # A node whose last successful poll is older than this is treated as down.
    stale_after_s: float = 10.0
    agent_token: str | None = None
    estimate: EstimateConfig = field(default_factory=EstimateConfig)
    busy: BusyConfig = field(default_factory=BusyConfig)

    @property
    def nodes_by_priority(self) -> list[NodeConfig]:
        return sorted(self.nodes, key=lambda n: n.priority)


def _strip_slash(url: str | None) -> str | None:
    return url.rstrip("/") if url else url


def parse_config(raw: dict[str, Any]) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")

    raw_nodes = raw.get("nodes") or []
    if not raw_nodes:
        raise ConfigError("config needs at least one entry under 'nodes'")

    nodes: list[NodeConfig] = []
    seen: set[str] = set()
    for i, n in enumerate(raw_nodes):
        if not isinstance(n, dict) or "name" not in n or "ollama_url" not in n:
            raise ConfigError(f"nodes[{i}] needs 'name' and 'ollama_url'")
        if n["name"] in seen:
            raise ConfigError(f"duplicate node name {n['name']!r}")
        seen.add(n["name"])
        nodes.append(
            NodeConfig(
                name=str(n["name"]),
                ollama_url=_strip_slash(str(n["ollama_url"])),
                agent_url=_strip_slash(n.get("agent_url")),
                priority=int(n.get("priority", 100 + i)),
                reserve_mb=int(n.get("reserve_mb", 512)),
            )
        )

    listen = raw.get("listen") or {}
    est = raw.get("estimate") or {}
    busy = raw.get("busy") or {}
    poll = float(raw.get("poll_interval_s", 2.0))

    return Config(
        nodes=nodes,
        host=str(listen.get("host", "0.0.0.0")),
        port=int(listen.get("port", 11434)),
        poll_interval_s=poll,
        stale_after_s=float(raw.get("stale_after_s", max(10.0, poll * 5))),
        agent_token=raw.get("agent_token"),
        estimate=EstimateConfig(
            overhead_factor=float(est.get("overhead_factor", 1.2)),
            overhead_mb=int(est.get("overhead_mb", 512)),
        ),
        busy=BusyConfig(
            gpu_util_percent=busy.get("gpu_util_percent", 85),
            consecutive_polls=int(busy.get("consecutive_polls", 3)),
        ),
    )


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as f:
        return parse_config(yaml.safe_load(f) or {})
