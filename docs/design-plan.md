# Nexus VRAM Router — Design Plan

## Context
The motivating setup is two Windows PCs on a home LAN, both running Ollama: an RTX 4080 Super (16 GB) that is also the gaming PC, and an RTX 2070 Super (8 GB). The goal is one Ollama endpoint for all AI apps that sends each request to the best GPU: the 4080 when it has room for the model, and the 2070 when a game is holding the 4080's VRAM. Apps must not be able to tell it isn't a normal Ollama server. Any number of machines must be supported, not just two.

Python 3.12+. Implementation status is tracked on the Backlog board.

**Decisions:**
- Both GPU machines run Windows.
- The router runs on a separate always-on Linux box, deployed with Docker Compose.
- Routing policy: try machines in priority order and use the first one where the model fits. If none fit, use the one with the most free VRAM.

## Architecture
```
apps ──► router (always-on box, Docker, :11434, looks like Ollama)
            │  polls every ~2s
            ├─► PC1: agent :11500 (nvidia-smi)  + Ollama :11434
            ├─► PC2: agent :11500 (nvidia-smi)  + Ollama :11434
            └─► PCn ...
```
- **Why each PC needs an agent:** Ollama's API only reports VRAM that Ollama itself is using. It can't see VRAM taken by a game. The agent is a tiny HTTP service that runs `nvidia-smi` and reports the GPU's total, used and free memory and its utilization.
- **Router:** a FastAPI app that copies Ollama's API. It reads `model` from the request body, picks a machine, and streams the response straight through.

## Layout
```
pyproject.toml                 # deps: fastapi, uvicorn, httpx, pyyaml; dev: pytest, pytest-asyncio, respx
config.example.yaml            # documented example; copied to config.yaml (git-ignored) for real use
Dockerfile, .dockerignore, docker-compose.yml
src/nexus_router/
  config.py      # load and check YAML: nodes, poll interval, estimate settings, busy threshold
  agent.py       # standard library only, one file, so it can be copied to Windows with nothing else installed
  poller.py      # background task: per node, polls agent /vram, Ollama /api/ps and /api/tags → NodeState
  estimator.py   # how much VRAM a model needs on a given node
  selector.py    # routing policy (pure functions, unit-tested)
  proxy.py       # FastAPI app: copied Ollama endpoints, streaming passthrough, failover
  main.py        # CLI: `nexus-router --config ...` (runs uvicorn on listen.host/port)
windows/
  install-agent.ps1    # adds a firewall rule for 11500 and a Scheduled Task that runs the agent at startup (pythonw)
  uninstall-agent.ps1
tests/  test_selector.py, test_estimator.py, test_proxy.py (respx-mocked nodes), test_agent.py (parse nvidia-smi CSV)
README.md  # setup for the Windows PCs + the Docker host, and how to point apps at the router
```

## Key behavior

**Agent** (`agent.py`): `GET /vram` runs `nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits` and returns JSON listing each GPU (values in MiB and percent). It has an optional `--token` shared secret. It uses only the standard library (`http.server` + `subprocess`), so Windows needs nothing beyond Python.

**Effective free VRAM per node:** `gpu_free + VRAM Ollama is using (from /api/ps) − reserve_mb`. VRAM that Ollama is using counts as free because Ollama unloads idle models to make room. VRAM a game is using does not count. Ollama reports sizes in bytes and the agent in MiB; convert at one boundary.

**Model VRAM estimate** (`estimator.py`):
- If the model is already loaded on that node, use its `size_vram` from `/api/ps`. It already fits there.
- Otherwise use `file size from /api/tags × overhead_factor (1.2) + overhead_mb (512)`. Both numbers can be changed in config.

**Selection** (`selector.py`):
1. Candidates are nodes that are healthy (agent and Ollama both responded within `stale_after_s`), have the model pulled, and are not busy.
2. Return the first candidate in priority order where the model fits.
3. If none fit, return the candidate with the most effective free VRAM. Ollama will then run part of the model on the CPU, which is slower but still works.
4. If no node has the model, send the request to the highest-priority healthy node so Ollama returns its own "model not found" error.

A node configured without `agent_url` has unknown VRAM: it is healthy if Ollama responds, never counts as "fits" in step 2 (unless the model is already loaded there), and is ranked after all measured nodes in step 3. The same applies to a node whose agent is down or returns an error.

Further decisions:
- With several GPUs on one node, free VRAM and Ollama-held VRAM are summed (Ollama can split a model across GPUs); busy uses the highest utilization.
- Effective free VRAM is clamped at 0.
- If every node that has the model is busy, the request is still routed to one of them (ranked by the normal fit rules) rather than failing, since a slow answer beats an error. Busy nodes otherwise rank after all idle nodes that have the model, and stay in the failover list.
- If no node is healthy, all nodes are tried in priority order (poll data may just be stale); if none connects the client gets `502 {"error": ...}`.
- The poller runs one independent loop per node, so a slow node never delays the others. A node is healthy when both `/api/tags` and `/api/ps` answered within `stale_after_s`; an agent failure only makes its VRAM unknown.
- Aggregated endpoints (`/api/tags`, `/api/ps`, `/v1/models`) are fetched live from each healthy node and de-duplicated by (normalized) name, higher priority first. They carry no `X-Nexus-Node` header.
- A node is marked busy only when its in-flight count is 0, so the streak resets while the router itself is using the node.

A node is **busy** when GPU utilization is above `busy.gpu_util_percent` (default 85) for 3 polls in a row while the router has no requests running on it. This catches a game that uses little VRAM but a lot of GPU. Set the threshold to null to turn this off.

**Endpoints copied from Ollama** (`proxy.py`):

| Kind | Endpoints | Router behavior |
|---|---|---|
| Model-routed | `POST /api/generate`, `/api/chat`, `/api/embed`, `/api/embeddings`, `/api/show`, `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings` | Pick a node with the selector |
| Aggregated | `GET /api/tags`, `/api/ps`, `/v1/models` | Combine results from all nodes, removing duplicates by model name |
| Fan-out | `POST /api/pull`, `DELETE /api/delete` | Send to every healthy node. Stream the primary node's progress; log the others' results |
| Simple | `GET /` returns "Ollama is running"; `HEAD /`; `GET /api/version` | Answered from the primary node |
| Other | anything else | Forwarded to the highest-priority healthy node |

Router-only endpoints (not part of Ollama's API):

| Endpoint | Purpose |
|---|---|
| `GET /router/health` | `200 {"status":"ok"}` whenever the router process is up, without touching any node. Used by the Docker healthcheck. |
| `GET /router/status` | Each node's state (health, GPUs, effective free VRAM, loaded models, busy, in-flight) and the last routing decisions. |

- **Streaming:** `httpx.AsyncClient.stream` feeding a `StreamingResponse(aiter_raw())`. It keeps the status code and content-type, and has no read timeout because loading a model can take a while.
- **Failover:** if connecting to the chosen node fails before any response bytes are sent, retry on the next candidate.
- Every routed response gets an `X-Nexus-Node: <name>` header.
- An in-flight counter per node feeds the busy check.

**Config** (`config.example.yaml`):
```yaml
listen: {host: 0.0.0.0, port: 11434}
poll_interval_s: 2
agent_token: null
estimate: {overhead_factor: 1.2, overhead_mb: 512}
busy: {gpu_util_percent: 85, consecutive_polls: 3}
nodes:
  - {name: rtx4080, ollama_url: "http://192.168.1.10:11434", agent_url: "http://192.168.1.10:11500", priority: 1, reserve_mb: 1024}
  - {name: rtx2070, ollama_url: "http://192.168.1.11:11434", agent_url: "http://192.168.1.11:11500", priority: 2, reserve_mb: 512}
```
To add more PCs, add more entries under `nodes`.

## Deployment

**GPU nodes (Windows):** each PC needs `OLLAMA_HOST=0.0.0.0` so Ollama accepts connections from the LAN, Python 3.10+, and the agent installed with `install-agent.ps1` (firewall rule for TCP 11500 + a Scheduled Task that starts `pythonw agent.py` at boot). Until that script exists the agent can be run by hand with `python agent.py --port 11500`.

**Router (Docker, always-on Linux box):**
- `Dockerfile`: two stages on `python:3.13-slim`. The build stage `pip install .` into `/opt/venv`; the runtime stage copies only the venv, runs as a non-root `nexus` user (UID 10001), exposes 11434, and has a `HEALTHCHECK` that calls `/router/health` with the stdlib so no curl is needed. `ENTRYPOINT ["nexus-router"]`, `CMD ["--config", "/config/config.yaml"]`.
- `.dockerignore`: the build context is only `pyproject.toml`, `README.md`, `LICENSE` and `src/`. Real `config.yaml` files are excluded so tokens are never baked into an image.
- `docker-compose.yml`: one `nexus-router` service, `restart: unless-stopped`, host port `${NEXUS_PORT:-11434}` → 11434, `./config.yaml` mounted read-only at `/config/config.yaml`, rotated json-file logs. Default bridge networking is enough: the router only makes outbound connections to LAN IPs, and needs no GPU.
- Config changes take effect with `docker compose restart`.

The router container is not meant to run on a GPU node that also serves Ollama on 11434; if it must, set `NEXUS_PORT` to another port.

## Verification
1. Unit tests: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest`
   - Selector cases: the 4080 has room; the 4080 is full from gaming, so the request goes to the 2070; the model is already loaded; nothing fits, so most free wins; a node is unhealthy or busy; a node without an agent; three or more nodes.
   - Estimator math, including bytes/MiB conversion.
   - Parsing of nvidia-smi CSV, including output with several GPUs and `[N/A]` fields.
   - Proxy tests against mocked nodes: streaming chunks arrive in order, failover works, `/api/tags` combines correctly, the `X-Nexus-Node` header is set, and `/router/health` answers with every node down.
2. Local smoke test on a Linux dev box with nvidia-smi:
   - Run `nexus-agent` and `curl :11500/vram`.
   - Run the router with a config pointing at a local Ollama (or a fake one), then run `curl /api/chat` with `stream:true` and check `/router/status`.
3. Container:
   - `docker compose config --quiet` validates the compose file.
   - `docker compose up -d --build`, then `docker compose ps` shows the service `healthy` and `curl http://<box>:11434/` returns `Ollama is running`.
4. Real test:
   - Point an app at `http://<box>:11434`.
   - Start a game on the 4080 PC and send a chat request. The `X-Nexus-Node` header should say `rtx2070`.
   - Close the game and send another request. It should go back to `rtx4080`.
