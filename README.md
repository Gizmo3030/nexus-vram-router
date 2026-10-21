# nexus-vram-router

**One Ollama endpoint for all your GPUs. Each request goes to the machine that has room for the model right now.**

[![tests](https://github.com/Gizmo3030/nexus-vram-router/actions/workflows/tests.yml/badge.svg)](https://github.com/Gizmo3030/nexus-vram-router/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)
![Status: in development](https://img.shields.io/badge/status-in%20development-orange.svg)

nexus-vram-router is a drop-in proxy for [Ollama](https://ollama.com). Point your apps at it instead of at a single Ollama server. For every request it checks how much VRAM is free on each of your machines and sends the request to the fastest one the model fits on.

It was built for a common home-lab situation: your best GPU is in your gaming PC. When you're not gaming, you want AI requests to use it. When a game is holding its VRAM, they should quietly move to a second machine instead of slowing the game down or failing.

> [!IMPORTANT]
> **This project is in early development.** The agent, router and Docker image work and are covered by tests, but they haven't been tested end to end on real machines yet, and the Windows install scripts have never been run on Windows. See [Project status](#project-status).

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Using the router](#using-the-router)
- [Routing in detail](#routing-in-detail)
- [Agent API](#agent-api)
- [Security](#security)
- [Development](#development)
- [Project status](#project-status)
- [License](#license)

## Features

- **Fully transparent.** Speaks Ollama's native API (`/api/*`) and its OpenAI-compatible API (`/v1/*`), including streaming. Apps can't tell it apart from a normal Ollama server.
- **Game-aware.** Measures real GPU memory with `nvidia-smi`, so VRAM taken by games and other apps is counted, not just what Ollama uses.
- **Priority with fallback.** Prefers your fastest GPU whenever the model fits there, and falls back to the next one when it doesn't.
- **Any number of nodes.** Add a machine by adding three lines of config.
- **Model-aware.** Only routes to nodes that have the model pulled. Prefers nodes where it's already loaded, so you don't wait for a reload.
- **Failover.** If a node can't be reached, the request is retried on the next candidate before any response is sent.
- **Unified model list.** `/api/tags`, `/api/ps` and `/v1/models` show models from every node combined.
- **Easy to inspect.** Every response carries an `X-Nexus-Node` header naming the machine that served it, and `/router/status` shows live state for every node.
- **Simple to deploy.** The router runs as one Docker container. The agent on each GPU machine is a single Python file with no dependencies.

## How it works

```
 apps (Open WebUI,       ┌────────────────────────────────┐
 Continue, scripts,  ──► │ nexus-router  (Docker, :11434) │
 OpenAI SDKs, ...)       │ looks exactly like Ollama      │
                         └───────────────┬────────────────┘
                                         │ polls every 2s, proxies requests
           ┌─────────────────────────────┼─────────────────────────────┐
           ▼                             ▼                             ▼
 ┌────────────────────┐        ┌────────────────────┐        ┌────────────────────┐
 │ PC 1  (priority 1) │        │ PC 2  (priority 2) │        │ PC n  ...          │
 │ RTX 4080 Super     │        │ RTX 2070 Super     │        │ any NVIDIA GPU     │
 │ Ollama      :11434 │        │ Ollama      :11434 │        │ Ollama      :11434 │
 │ nexus-agent :11500 │        │ nexus-agent :11500 │        │ nexus-agent :11500 │
 └────────────────────┘        └────────────────────┘        └────────────────────┘
```

There are two parts:

1. **`nexus-agent`** runs on each GPU machine and reports free VRAM and GPU utilization from `nvidia-smi`. It's needed because Ollama's own API only knows about VRAM that Ollama is using. It can't see a game.
2. **`nexus-router`** runs on an always-on machine. It polls every agent, plus every Ollama's `/api/ps` and `/api/tags`. When a request arrives it reads the `model` field, picks a node, and streams the response back unchanged.

## Requirements

| Where | What you need |
|---|---|
| Each GPU machine | NVIDIA GPU and driver (`nvidia-smi` on `PATH`), [Ollama](https://ollama.com/download) reachable on the LAN, Python 3.10+ for the agent |
| Router host | Docker with Docker Compose, or Python 3.12+ |
| Network | The router host can reach TCP 11434 (Ollama) and 11500 (agent) on every GPU machine |

GPU machines can run Windows or Linux. The router doesn't need a GPU.

## Quick start

### 1. Prepare each GPU machine

**Let Ollama accept LAN connections.** On Windows, set a user environment variable, then quit and restart Ollama from the tray:

```powershell
setx OLLAMA_HOST 0.0.0.0
```

**Install the agent.** Copy [`src/nexus_router/agent.py`](src/nexus_router/agent.py) and [`windows/install-agent.ps1`](windows/install-agent.ps1) into one folder on the machine (the agent is a single file with no dependencies), then run in an elevated PowerShell:

```powershell
.\install-agent.ps1                                  # port 11500, no token
.\install-agent.ps1 -Port 11500 -Token mysecret      # or with a shared secret (set agent_token in the router config)
```

The script copies the agent to `%ProgramData%\nexus-agent`, opens the port on the Private network profile, and registers a Scheduled Task that starts the agent at boot. Running it again replaces the task and the rule instead of adding more. Remove everything with `windows\uninstall-agent.ps1`. Python must be installed for all users (the task runs as SYSTEM); pass `-Python <path to pythonw.exe>` if `pythonw` isn't on `PATH`.

To try the agent without installing it: `python agent.py --port 11500`.

From the router host, check that it responds:

```bash
curl http://192.168.1.10:11500/vram
```


### 2. Run the router

On your always-on machine:

```bash
git clone https://github.com/Gizmo3030/nexus-vram-router.git
cd nexus-vram-router
cp config.example.yaml config.yaml      # edit node names, IPs and priorities
docker compose up -d --build
```

Check it:

```bash
docker compose ps                        # STATUS should show (healthy)
curl http://localhost:11434/             # Ollama is running
curl http://localhost:11434/router/status
```

After editing `config.yaml`, run `docker compose restart` to apply the changes.

### 3. Point your apps at it

Anywhere you'd enter an Ollama URL, use the router instead:

```
http://<router-host>:11434
```

## Configuration

The router reads a YAML file. [`config.example.yaml`](config.example.yaml) is a fully commented starting point. Only `nodes` is required.

```yaml
nodes:
  - name: rtx4080
    ollama_url: http://192.168.1.10:11434
    agent_url: http://192.168.1.10:11500
    priority: 1
    reserve_mb: 1024
  - name: rtx2070
    ollama_url: http://192.168.1.11:11434
    agent_url: http://192.168.1.11:11500
    priority: 2
```

### Settings

| Key | Default | Description |
|---|---|---|
| `listen.host` | `0.0.0.0` | Address the router listens on |
| `listen.port` | `11434` | Port the router listens on. Ollama's default, so apps only need a new host |
| `poll_interval_s` | `2` | Seconds between polls of each node |
| `stale_after_s` | `max(10, 5 × poll_interval_s)` | A node that hasn't answered for this long is treated as down |
| `agent_token` | `null` | Shared secret sent to agents as `Authorization: Bearer …` |
| `estimate.overhead_factor` | `1.2` | Multiplier on a model's file size to estimate the VRAM it needs |
| `estimate.overhead_mb` | `512` | Fixed extra MiB added to that estimate (context, KV cache) |
| `busy.gpu_util_percent` | `85` | GPU utilization above which a node counts as busy. `null` turns this off |
| `busy.consecutive_polls` | `3` | How many polls in a row utilization must stay high |

### Node settings

| Key | Required | Default | Description |
|---|---|---|---|
| `name` | yes | — | Unique name. Appears in `X-Nexus-Node` and `/router/status` |
| `ollama_url` | yes | — | Base URL of the node's Ollama |
| `agent_url` | no | — | Base URL of the node's agent. Without it, the node's VRAM is unknown and it's only used as a last resort |
| `priority` | no | 100 + position | Lower numbers are tried first |
| `reserve_mb` | no | `512` | VRAM to always leave free on this node, for example for the desktop or a game's spikes |

### Environment variables (Docker Compose)

| Variable | Default | Description |
|---|---|---|
| `NEXUS_PORT` | `11434` | Host port that is published for the router |
| `TZ` | `UTC` | Container time zone, used for log timestamps |

## Using the router

The router answers like Ollama, so the usual tools work unchanged.

**Ollama CLI** (from any machine):

```bash
OLLAMA_HOST=http://router-host:11434 ollama run llama3.1
```

**Native API:**

```bash
curl http://router-host:11434/api/chat -d '{
  "model": "llama3.1",
  "messages": [{"role": "user", "content": "Hello!"}]
}'
```

**OpenAI-compatible clients:** set the base URL to `http://router-host:11434/v1`. The API key can be any string.

```python
from openai import OpenAI

client = OpenAI(base_url="http://router-host:11434/v1", api_key="ollama")
reply = client.chat.completions.create(
    model="llama3.1",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

**Apps** such as Open WebUI, Continue or AnythingLLM: set their Ollama URL to `http://router-host:11434`.

### Which node served my request?

```bash
curl -si http://router-host:11434/api/generate \
  -d '{"model":"llama3.1","prompt":"hi","stream":false}' | grep -i x-nexus-node
# X-Nexus-Node: rtx2070
```

`GET /router/status` shows each node's health, free VRAM, loaded models and busy state, plus recent routing decisions.

### Endpoint behavior

| Endpoints | What the router does |
|---|---|
| `/api/generate`, `/api/chat`, `/api/embed`, `/api/embeddings`, `/api/show`, `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings` | Sends the request to the best node for the `model` |
| `/api/tags`, `/api/ps`, `/v1/models` | Combines results from all nodes |
| `/api/pull`, `/api/delete` | Runs on every healthy node, so models stay in sync |
| `/`, `/api/version`, everything else | Forwards to the highest-priority healthy node |
| `/router/health`, `/router/status` | Handled by the router itself, not part of Ollama |

## Routing in detail

For each request the router:

1. **Filters** to nodes that are reachable, have the model pulled, and aren't busy.
2. **Estimates** how much VRAM the model needs on each of those nodes:
   - If the model is already loaded there, it fits.
   - Otherwise the estimate is `file size × overhead_factor + overhead_mb`.
3. **Compares** that with each node's *effective free VRAM*: GPU free memory, plus memory Ollama holds (Ollama unloads idle models to make room), minus `reserve_mb`. Memory used by a game doesn't count as free.
4. **Picks** the first node in priority order where the model fits.
5. **Falls back**, if it fits nowhere, to the node with the most effective free VRAM. Ollama then runs part of the model on the CPU, which is slower but still answers.

A node is **busy** if its GPU utilization stays above `busy.gpu_util_percent` while the router isn't sending it any work. This catches GPU-heavy games that leave VRAM free.

If no node has the model, the request goes to the highest-priority node so Ollama returns its normal "model not found" error.

The full design, including edge cases, is in [docs/design-plan.md](docs/design-plan.md).

## Agent API

`GET /vram` returns all GPUs on the machine. Memory is in MiB.

```json
{
  "gpus": [
    {
      "index": 0,
      "name": "NVIDIA GeForce RTX 4080 SUPER",
      "total_mb": 16376,
      "used_mb": 11250,
      "free_mb": 4812,
      "util_percent": 97
    }
  ]
}
```

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Address to listen on |
| `--port` | `11500` | Port to listen on |
| `--token` | none | If set, requests must send `Authorization: Bearer <token>` |
| `--nvidia-smi` | `nvidia-smi` | Path to `nvidia-smi`, if it isn't on `PATH` |

If `nvidia-smi` fails, the agent returns HTTP 500 with an `error` message, and the router treats that node's VRAM as unknown.

## Security

The router, like Ollama, has **no authentication**. It's meant for a trusted home or lab network:

- Don't expose port 11434 or 11500 to the internet. Limit the firewall rule to your private network profile.
- Set `agent_token` in the config and start each agent with `--token` so only your router can read GPU data.
- `config.yaml` is mounted into the container at runtime and excluded from the Docker build context, so tokens are never baked into the image. Keep it out of version control.
- The container runs as an unprivileged user and needs no GPU access or extra capabilities.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest

.venv/bin/nexus-agent --port 11500           # then: curl localhost:11500/vram
.venv/bin/nexus-router --config config.yaml
```

Tests use `pytest-asyncio` and `respx`. They don't need a GPU, network access or a running Ollama.

```
src/nexus_router/
  agent.py       standalone VRAM agent (stdlib only)
  config.py      YAML config loading and validation
  poller.py      polls agents and Ollama for node state
  estimator.py   VRAM-needed estimates per model
  selector.py    routing policy (pure functions)
  proxy.py       Ollama-compatible FastAPI app
  main.py        command-line entry point
docs/            design documents
windows/         agent install scripts for Windows
```

Contributor and AI-agent conventions are in [AGENTS.md](AGENTS.md). Work is tracked with [Backlog.md](https://github.com/MrLesk/Backlog.md) in `backlog/`.

## Project status

| Component | Status |
|---|---|
| VRAM agent (`agent.py`) | ✅ Working (Windows/`pythonw` run not yet confirmed) |
| Config loading (`config.py`, `config.example.yaml`) | ✅ Working |
| Poller, estimator, selector, busy detection | ✅ Working |
| Ollama-compatible proxy and `main.py` | ✅ Working |
| Tests | ✅ Unit and mocked-node tests |
| Windows install scripts | 🚧 Written, untested on Windows |
| Docker image and Compose file | ✅ Built and run: healthy, non-root |
| End-to-end test on the real machines | 📋 Not done |

## License

[MIT](LICENSE) © 2026 Gizmo
