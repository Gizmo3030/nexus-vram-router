from __future__ import annotations

import httpx
import pytest

from nexus_router.config import BusyConfig, Config, NodeConfig

MIB = 1024 * 1024


def make_config(**kw) -> Config:
    nodes = kw.pop("nodes", None) or [
        NodeConfig("fast", "http://fast:11434", "http://fast:11500", priority=1, reserve_mb=0),
        NodeConfig("slow", "http://slow:11434", "http://slow:11500", priority=2, reserve_mb=0),
    ]
    return Config(nodes=nodes, **kw)


def mock_node(router, host: str, *, free_mb=10000, util=0, models=("llama3:latest",), loaded=None,
              size_mb=4000, agent=True, ollama=True):
    """Register Ollama + agent routes for `host` on a respx router."""
    if ollama:
        router.get(f"http://{host}:11434/api/tags").respond(
            json={"models": [{"name": m, "size": size_mb * MIB} for m in models]})
        router.get(f"http://{host}:11434/api/ps").respond(
            json={"models": [{"name": m, "size": v * MIB, "size_vram": v * MIB} for m, v in (loaded or {}).items()]})
    else:
        for p in ("tags", "ps"):
            router.get(f"http://{host}:11434/api/{p}").mock(side_effect=httpx.ConnectError("down"))
    if agent is True:
        router.get(f"http://{host}:11500/vram").respond(json={"gpus": [
            {"index": 0, "name": "gpu", "total_mb": 16000, "used_mb": 16000 - free_mb,
             "free_mb": free_mb, "util_percent": util}]})
    elif agent == "error":
        router.get(f"http://{host}:11500/vram").respond(500, json={"error": "nvidia-smi failed"})


@pytest.fixture
def busy_cfg():
    return BusyConfig(gpu_util_percent=85, consecutive_polls=3)
