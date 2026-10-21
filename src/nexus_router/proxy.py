"""The Ollama-compatible FastAPI app: routes model requests, streams responses unchanged."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from .config import Config
from .estimator import normalize_model
from .poller import Poller
from .selector import select

log = logging.getLogger("nexus_router")

MODEL_ROUTES = [
    "/api/generate",
    "/api/chat",
    "/api/embed",
    "/api/embeddings",
    "/api/show",
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/embeddings",
]
ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
              "proxy-authenticate", "proxy-authorization"}
# Connecting is fast or it's down; reading is not (a model load can take minutes).
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=None, write=None, pool=None)
AGGREGATE_TIMEOUT = httpx.Timeout(10.0)
# Failures that happen before the node sent anything, so trying another node is safe.
RETRYABLE = (httpx.ConnectError, httpx.ConnectTimeout)


def _request_headers(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP | {"host", "content-length"}}


def _model_of(body: bytes) -> str | None:
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    # /api/show and /api/pull historically used "name".
    model = data.get("model") or data.get("name")
    return model if isinstance(model, str) and model else None


def create_app(config: Config, client: httpx.AsyncClient | None = None, poll: bool = True) -> FastAPI:
    client = client or httpx.AsyncClient(timeout=PROXY_TIMEOUT)
    poller = Poller(config, client)
    decisions: deque[dict] = deque(maxlen=50)
    background: set[asyncio.Task] = set()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if poll:
            poller.start()
        try:
            yield
        finally:
            await poller.stop()
            for t in list(background):
                t.cancel()
            await client.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.poller = poller
    app.state.decisions = decisions

    def priority_order(healthy_only: bool = True) -> list[str]:
        views = sorted(poller.views(), key=lambda v: (v.priority, v.name))
        names = [v.name for v in views if v.healthy or not healthy_only]
        return names or [v.name for v in views]

    def healthy_names() -> list[str]:
        return [v.name for v in sorted(poller.views(), key=lambda v: (v.priority, v.name)) if v.healthy]

    async def forward(request: Request, body: bytes, names: list[str]) -> Response:
        """Send the request to the first reachable node in `names` and stream the answer back.
        Failover happens only while connecting; once a node has answered we are committed."""
        path = request.scope.get("raw_path", b"").decode() or request.url.path
        query = request.url.query
        headers = _request_headers(request)
        last_error: Exception | None = None
        for name in names:
            state = poller.states[name]
            url = state.cfg.ollama_url + path + (f"?{query}" if query else "")
            state.in_flight += 1
            try:
                req = client.build_request(request.method, url, headers=headers, content=body or None)
                resp = await client.send(req, stream=True)
            except RETRYABLE as e:
                state.in_flight -= 1
                last_error = e
                log.warning("node %s: connect failed (%s); trying next", name, type(e).__name__)
                continue
            except BaseException:
                state.in_flight -= 1
                raise

            async def stream(resp=resp, state=state):
                try:
                    async for chunk in resp.aiter_raw():
                        yield chunk
                finally:
                    await resp.aclose()
                    state.in_flight -= 1

            out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}
            out_headers["X-Nexus-Node"] = name
            return StreamingResponse(stream(), status_code=resp.status_code, headers=out_headers)
        detail = f": {type(last_error).__name__}" if last_error else ""
        return JSONResponse({"error": f"no reachable Ollama node{detail}"}, status_code=502)

    # -- router-only endpoints ---------------------------------------------------------------

    @app.get("/router/health")
    async def health():
        return {"status": "ok"}

    @app.get("/router/status")
    async def status():
        nodes = []
        for state in poller.states.values():
            view = poller.view(state)
            nodes.append(
                {
                    "name": state.cfg.name,
                    "priority": state.cfg.priority,
                    "healthy": view.healthy,
                    "busy": state.busy,
                    "in_flight": state.in_flight,
                    "gpus": state.gpus,
                    "effective_free_mb": view.free_mb,
                    "loaded_models": sorted(state.loaded),
                    "models": sorted(state.models),
                }
            )
        return {"nodes": nodes, "recent_decisions": list(decisions)}

    # -- simple endpoints --------------------------------------------------------------------

    @app.api_route("/", methods=["GET", "HEAD"])
    async def root():
        return PlainTextResponse("Ollama is running")

    # -- aggregated endpoints ----------------------------------------------------------------

    async def fetch_all(path: str) -> list[dict]:
        names = healthy_names()

        async def one(name: str):
            r = await client.get(poller.states[name].cfg.ollama_url + path, timeout=AGGREGATE_TIMEOUT)
            r.raise_for_status()
            return r.json()

        results = await asyncio.gather(*(one(n) for n in names), return_exceptions=True)
        return [r for r in results if not isinstance(r, BaseException)]

    def merge(results: list[dict], list_key: str, id_key: str, extra: dict | None = None) -> dict:
        seen, items = set(), []
        for r in results:  # results are in priority order
            for item in r.get(list_key, []):
                key = normalize_model(item.get(id_key, "")) if id_key != "id" else item.get(id_key)
                if key not in seen:
                    seen.add(key)
                    items.append(item)
        return {**(extra or {}), list_key: items}

    @app.get("/api/tags")
    async def tags():
        return merge(await fetch_all("/api/tags"), "models", "name")

    @app.get("/api/ps")
    async def ps():
        return merge(await fetch_all("/api/ps"), "models", "name")

    @app.get("/v1/models")
    async def v1_models():
        return merge(await fetch_all("/v1/models"), "data", "id", {"object": "list"})

    # -- model-routed endpoints --------------------------------------------------------------

    async def routed(request: Request) -> Response:
        body = await request.body()
        model = _model_of(body)
        decision = select(poller.views(), model, config.estimate)
        log.info("%s %s model=%s -> %s (%s)", request.method, request.url.path, model, decision.node, decision.reason)
        decisions.append(
            {
                "time": time.time(),
                "path": request.url.path,
                "model": model,
                "node": decision.node,
                "candidates": list(decision.candidates),
                "reason": decision.reason,
            }
        )
        return await forward(request, body, list(decision.candidates))

    for route in MODEL_ROUTES:
        app.add_api_route(route, routed, methods=["POST"])

    # -- fan-out endpoints -------------------------------------------------------------------

    async def fan_out_secondary(method: str, url: str, headers: dict, body: bytes, name: str) -> None:
        try:
            async with client.stream(method, url, headers=headers, content=body or None) as r:
                await r.aread()
            log.info("fan-out %s %s on %s -> %s", method, url, name, r.status_code)
        except Exception as e:
            log.warning("fan-out %s %s on %s failed: %r", method, url, name, e)

    async def fan_out(request: Request) -> Response:
        body = await request.body()
        names = healthy_names()
        if not names:
            return await forward(request, body, priority_order())
        path = request.scope.get("raw_path", b"").decode() or request.url.path
        headers = _request_headers(request)
        for name in names[1:]:
            url = poller.states[name].cfg.ollama_url + path
            task = asyncio.create_task(fan_out_secondary(request.method, url, headers, body, name))
            background.add(task)
            task.add_done_callback(background.discard)
        return await forward(request, body, names[:1])

    app.add_api_route("/api/pull", fan_out, methods=["POST"])
    app.add_api_route("/api/delete", fan_out, methods=["DELETE"])

    # -- everything else goes to the highest-priority healthy node ----------------------------

    @app.api_route("/{path:path}", methods=ALL_METHODS)
    async def passthrough(request: Request):
        return await forward(request, await request.body(), priority_order())

    return app
