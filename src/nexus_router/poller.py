"""Background polling: keeps every node's live state in memory so routing never waits on I/O."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .config import Config, NodeConfig
from .estimator import bytes_to_mb, normalize_model
from .selector import NodeView

log = logging.getLogger("nexus_router.poller")

# Polls are small and local; a node that takes longer than this is as good as down.
POLL_TIMEOUT = httpx.Timeout(5.0)


@dataclass
class NodeState:
    cfg: NodeConfig
    last_ok: float | None = None  # clock value of the last poll where Ollama answered fully
    gpus: list[dict] | None = None  # None: no agent, or it isn't answering
    models: dict[str, int] = field(default_factory=dict)  # normalized name -> file bytes
    loaded: dict[str, int] = field(default_factory=dict)  # normalized name -> size_vram bytes
    in_flight: int = 0
    high_util_polls: int = 0
    busy: bool = False


def effective_free_mb(gpus: list[dict] | None, loaded: dict[str, int], reserve_mb: int) -> int | None:
    """GPU free + VRAM Ollama holds (it evicts idle models) - reserve. Summed over GPUs
    because Ollama can spread a model across them."""
    if not gpus:
        return None
    frees = [g["free_mb"] for g in gpus if g.get("free_mb") is not None]
    if not frees:
        return None
    held = sum(bytes_to_mb(b) for b in loaded.values())
    return max(0, sum(frees) + held - reserve_mb)


class Poller:
    def __init__(self, config: Config, client: httpx.AsyncClient, clock: Callable[[], float] = time.monotonic):
        self.config = config
        self.client = client
        self.clock = clock
        self.states = {n.name: NodeState(n) for n in config.nodes}
        self._tasks: list[asyncio.Task] = []

    # -- views for the selector / status endpoint ------------------------------------------

    def is_healthy(self, state: NodeState) -> bool:
        return state.last_ok is not None and self.clock() - state.last_ok <= self.config.stale_after_s

    def view(self, state: NodeState) -> NodeView:
        return NodeView(
            name=state.cfg.name,
            priority=state.cfg.priority,
            healthy=self.is_healthy(state),
            busy=state.busy,
            free_mb=effective_free_mb(state.gpus, state.loaded, state.cfg.reserve_mb),
            models=state.models,
            loaded=state.loaded,
        )

    def views(self) -> list[NodeView]:
        return [self.view(s) for s in self.states.values()]

    # -- polling -------------------------------------------------------------------------------

    async def _get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        resp = await self.client.get(url, headers=headers, timeout=POLL_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def poll_node(self, state: NodeState) -> None:
        cfg = state.cfg
        agent_headers = {"Authorization": f"Bearer {self.config.agent_token}"} if self.config.agent_token else None
        calls = [self._get_json(f"{cfg.ollama_url}/api/tags"), self._get_json(f"{cfg.ollama_url}/api/ps")]
        if cfg.agent_url:
            calls.append(self._get_json(f"{cfg.agent_url}/vram", agent_headers))
        tags, ps, *agent = await asyncio.gather(*calls, return_exceptions=True)

        if not isinstance(tags, BaseException) and not isinstance(ps, BaseException):
            try:
                state.models = {normalize_model(m["name"]): int(m.get("size", 0)) for m in tags["models"]}
                state.loaded = {normalize_model(m["name"]): int(m.get("size_vram", 0)) for m in ps["models"]}
                state.last_ok = self.clock()
            except (KeyError, TypeError, ValueError) as e:
                log.warning("node %s: unexpected Ollama response: %r", cfg.name, e)
        else:
            err = tags if isinstance(tags, BaseException) else ps
            log.warning("node %s: Ollama poll failed: %r", cfg.name, err)

        state.gpus = None
        if agent:
            result = agent[0]
            if isinstance(result, BaseException):
                log.warning("node %s: agent poll failed: %r", cfg.name, result)
            elif isinstance(result, dict) and isinstance(result.get("gpus"), list):
                state.gpus = result["gpus"]
            else:
                log.warning("node %s: unexpected agent response", cfg.name)
        self._update_busy(state)

    def _update_busy(self, state: NodeState) -> None:
        threshold = self.config.busy.gpu_util_percent
        utils = [g["util_percent"] for g in (state.gpus or []) if g.get("util_percent") is not None]
        # Utilization while the router itself is running requests there is our own load, not a game's.
        if threshold is not None and utils and max(utils) > threshold and state.in_flight == 0:
            state.high_util_polls += 1
        else:
            state.high_util_polls = 0
        state.busy = state.high_util_polls >= self.config.busy.consecutive_polls

    async def poll_all(self) -> None:
        await asyncio.gather(*(self.poll_node(s) for s in self.states.values()))

    async def _loop(self, state: NodeState) -> None:
        # One loop per node so a slow or offline node never delays the others.
        while True:
            try:
                await self.poll_node(state)
            except Exception:
                log.exception("node %s: poll crashed", state.cfg.name)
            await asyncio.sleep(self.config.poll_interval_s)

    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._loop(s)) for s in self.states.values()]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
