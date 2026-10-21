"""Routing policy. Pure: takes node snapshots, returns an ordered decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .config import EstimateConfig
from .estimator import estimate_mb, normalize_model


@dataclass(frozen=True)
class NodeView:
    name: str
    priority: int
    healthy: bool
    busy: bool = False
    # Effective free VRAM (GPU free + what Ollama holds - reserve); None when there is no agent
    # or it isn't answering.
    free_mb: int | None = None
    models: Mapping[str, int] = field(default_factory=dict)  # normalized name -> file size in bytes (/api/tags)
    loaded: Mapping[str, int] = field(default_factory=dict)  # normalized name -> size_vram in bytes (/api/ps)


@dataclass(frozen=True)
class Decision:
    candidates: tuple[str, ...]  # node names in the order to try; the first is the choice
    reason: str

    @property
    def node(self) -> str | None:
        return self.candidates[0] if self.candidates else None


def _rank(nodes: list[NodeView], model: str, est: EstimateConfig) -> list[NodeView]:
    """Nodes where the model fits (priority order), then the rest by most free VRAM;
    nodes with unknown VRAM come after every measured node."""
    fits, rest = [], []
    for n in nodes:
        e = estimate_mb(model, n.loaded, n.models, est)
        ok = e.loaded or (n.free_mb is not None and e.mb is not None and e.mb <= n.free_mb)
        (fits if ok else rest).append(n)
    rest.sort(key=lambda n: (n.free_mb is None, -(n.free_mb or 0), n.priority))
    return fits + rest


def select(nodes: Sequence[NodeView], model: str | None, est: EstimateConfig) -> Decision:
    ordered = sorted(nodes, key=lambda n: (n.priority, n.name))
    healthy = [n for n in ordered if n.healthy]
    if not healthy:
        # Poll data may just be stale; trying in priority order lets connect failover decide.
        return Decision(tuple(n.name for n in ordered), "no healthy node")

    if model is not None:
        m = normalize_model(model)
        have = [n for n in healthy if m in n.models or m in n.loaded]
        if have:
            # A busy node (e.g. a game is using the GPU) is only a last resort: it ranks
            # after every idle node that has the model, but is still preferred over a node
            # that would just answer "model not found".
            idle = _rank([n for n in have if not n.busy], m, est)
            busy = _rank([n for n in have if n.busy], m, est)
            names = tuple(n.name for n in idle + busy)
            first = (idle or busy)[0]
            e = estimate_mb(m, first.loaded, first.models, est)
            if not idle:
                reason = "every node with the model is busy"
            elif e.loaded:
                reason = "model already loaded"
            elif first.free_mb is not None and e.mb is not None and e.mb <= first.free_mb:
                reason = "fits"
            else:
                reason = "fits nowhere; most free VRAM"
            return Decision(names, reason)

    return Decision(tuple(n.name for n in healthy), "no node has the model" if model else "no model in request")
