"""How much VRAM a model needs on a node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .config import EstimateConfig

_MIB = 1024 * 1024


def bytes_to_mb(size_bytes: int) -> int:
    """Ollama reports bytes, the agent MiB; round up so estimates err on the safe side."""
    return -(-size_bytes // _MIB)


def normalize_model(name: str) -> str:
    """Ollama treats `llama3` as `llama3:latest`; the tag is whatever follows the last ':'
    after the last '/', so a registry port (`host:5000/m`) is not mistaken for a tag."""
    name = name.strip()
    if ":" not in name.rsplit("/", 1)[-1]:
        return f"{name}:latest"
    return name


@dataclass(frozen=True)
class Estimate:
    mb: int | None  # None: the node doesn't have the model, so there is nothing to estimate
    loaded: bool  # already in memory on the node, so it fits there by definition


def estimate_mb(
    model: str,
    loaded_bytes: Mapping[str, int],
    sizes_bytes: Mapping[str, int],
    est: EstimateConfig,
) -> Estimate:
    """`model` must already be normalized, as must the keys of both mappings."""
    if model in loaded_bytes:
        return Estimate(bytes_to_mb(loaded_bytes[model]), True)
    if model in sizes_bytes:
        return Estimate(int(bytes_to_mb(sizes_bytes[model]) * est.overhead_factor) + est.overhead_mb, False)
    return Estimate(None, False)
