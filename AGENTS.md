# nexus-vram-router — Agent Guide

An Ollama-compatible HTTP proxy. Apps talk to it exactly as they would to Ollama; for each request it picks the GPU machine (node) that has room for the requested model and streams the response back. The motivating setup: a Windows gaming PC (RTX 4080 Super) that is preferred when free, and a slower Windows PC (RTX 2070 Super) used when a game is holding the 4080's VRAM. The router itself runs in Docker on a separate always-on Linux box. Any number of nodes is supported.

**The design spec is [docs/design-plan.md](docs/design-plan.md).** Read it before changing routing, endpoints, or config. If you change the design, update that file in the same change.

## Status

Implemented: `config.py`, `agent.py`, `poller.py`, `estimator.py`, `selector.py`, `proxy.py`, `main.py`, `tests/`, `windows/*.ps1` (the scripts have never been run on Windows), plus the Docker files (image build and healthy container verified). `GET /router/health` is the Docker healthcheck.

Keep `README.md` (user-facing: setup, config reference, project status table) in sync when you add features, config keys, or endpoints. Check the Backlog board for what is in progress before starting new work.

## How it works (short version)

- **Agent** (`agent.py`) runs on each GPU node, serves `GET /vram` from `nvidia-smi`. Needed because Ollama's API can't see VRAM used by games.
- **Poller** polls every node's agent plus Ollama `/api/ps` and `/api/tags` every `poll_interval_s`.
- **Selector** picks a node: healthy + has the model + not busy → first in priority order where the model fits → else most effective free VRAM → if no node has the model, highest-priority healthy node (so Ollama returns its own error).
- **Effective free** = GPU free + VRAM Ollama currently holds (it evicts idle models) − `reserve_mb`.
- **Proxy** forwards requests and streams responses unchanged; adds only an `X-Nexus-Node` header and `/router/*` endpoints.

## Rules that must hold

1. **Transparency.** To a client the router is Ollama. Keep paths, methods, status codes, content types, and streamed bodies (NDJSON for `/api/*`, SSE for `/v1/*`) byte-for-byte as the node sent them. Never add or rename fields in Ollama responses. Router-specific things live only in the `X-Nexus-Node` header and under `/router/`.
2. **`agent.py` stays standalone.** Standard library only, no imports from the rest of the package, runs on Windows and Python 3.10+. It is copied to GPU machines as a single file.
3. **`selector.py` stays pure.** No I/O, no clock reads, no globals: it takes node state and returns a decision so it can be unit-tested exhaustively.
4. **N nodes, not two.** Never hardcode node count, names (`rtx4080`, `rtx2070`), or IPs in source. Those belong only in example config and tests.
5. **No read timeout on proxied requests.** Model loads can take minutes. Connect timeouts are fine and drive failover.
6. **Failover only before the first byte.** Once any response bytes have gone to the client, never retry on another node.

## Gotchas

- **Units differ.** `nvidia-smi --format=...,nounits` and the agent report **MiB**. Ollama `/api/tags` `size` and `/api/ps` `size_vram` are **bytes**. Convert at one boundary and name variables with their unit (`free_mb`, `size_bytes`).
- **Model names.** Ollama treats `llama3` as `llama3:latest`. Normalize before matching a request's `model` against `/api/tags` or `/api/ps`.
- **Where `model` lives.** It's a top-level JSON body field on all routed endpoints, including the OpenAI-compatible `/v1/*` ones. Bodies may be large (images base64-encoded); read the body once and forward the same bytes.
- **nvidia-smi output** can contain `[N/A]` / `[Not Supported]` fields and GPU names with commas; `parse_nvidia_smi` already handles both — extend its tests if you touch it.
- **Port 11434** is Ollama's default. The router uses it too so apps only change the host; don't run the router on a machine that is also serving Ollama on that port.

## Code conventions

Match the existing modules:
- `from __future__ import annotations`, modern type hints (`str | None`, `list[...]`).
- Config is frozen `@dataclass`es in `config.py`. Adding a config key means: dataclass field with a sensible default, parsing in `parse_config`, an entry in `config.example.yaml`, and a mention in the design doc. Invalid config raises `ConfigError` with a message naming the bad field.
- Async HTTP with one shared `httpx.AsyncClient`; FastAPI for the router.
- Short module docstrings; comments explain *why*, not *what*.

## Commands

No `uv` on the dev box; use a venv:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                  # tests (pytest-asyncio auto mode, respx for httpx mocks)
.venv/bin/nexus-agent --port 11500                # agent; then: curl localhost:11500/vram
.venv/bin/nexus-router --config config.yaml       # router (once main.py exists)
```

The dev box is Linux with an NVIDIA GPU, so the agent can be tested against real `nvidia-smi` here. Tests must not need a GPU, network access, or a running Ollama: feed `parse_nvidia_smi` sample strings and mock nodes with respx.

<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.55.0 -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**At the beginning of each conversation in this project, run `backlog instructions overview` before answering or taking action. Re-read it only if you have not read it yet in the current conversation.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->
