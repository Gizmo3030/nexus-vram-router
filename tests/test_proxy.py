import json

import httpx
import pytest
import respx

from conftest import make_config, mock_node
from nexus_router.proxy import create_app

NDJSON = b'{"response":"a"}\n{"response":"b"}\n{"done":true}\n'


@pytest.fixture
def mock():
    with respx.mock(assert_all_called=False) as m:
        yield m


async def client_for(mock, cfg=None, **node_kw):
    app = create_app(cfg or make_config(), poll=False)
    await app.state.poller.poll_all()
    return app, httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://router")


def setup_nodes(mock, fast=None, slow=None):
    mock_node(mock, "fast", **(fast or {}))
    mock_node(mock, "slow", **(slow or {}))


async def test_chat_routed_to_fastest_with_header_and_exact_body(mock):
    setup_nodes(mock)
    route = mock.post("http://fast:11434/api/chat").respond(200, content=NDJSON,
                                                              headers={"content-type": "application/x-ndjson"})
    _, c = await client_for(mock)
    payload = b'{"model": "llama3",  "messages":[], "stream":true}'  # odd spacing must survive
    r = await c.post("/api/chat", content=payload, headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert r.headers["x-nexus-node"] == "fast"
    assert r.headers["content-type"] == "application/x-ndjson"
    assert r.content == NDJSON
    assert route.calls[0].request.content == payload


async def test_goes_to_slow_when_fast_is_full(mock):
    setup_nodes(mock, fast={"free_mb": 100}, slow={"free_mb": 9000})
    mock.post("http://slow:11434/v1/chat/completions").respond(200, content=b"data: x\n\n",
                                                                headers={"content-type": "text/event-stream"})
    _, c = await client_for(mock)
    r = await c.post("/v1/chat/completions", json={"model": "llama3", "messages": []})
    assert r.headers["x-nexus-node"] == "slow"
    assert r.headers["content-type"] == "text/event-stream"
    assert r.content == b"data: x\n\n"


@pytest.mark.parametrize("path", ["/api/generate", "/api/chat", "/api/embed", "/api/embeddings", "/api/show",
                                  "/v1/chat/completions", "/v1/completions", "/v1/embeddings"])
async def test_all_model_routes(mock, path):
    setup_nodes(mock)
    mock.post(f"http://fast:11434{path}").respond(200, json={"ok": True})
    _, c = await client_for(mock)
    r = await c.post(path, json={"model": "llama3"})
    assert r.status_code == 200 and r.headers["x-nexus-node"] == "fast"


async def test_error_status_passes_through_without_failover(mock):
    setup_nodes(mock)
    mock.post("http://fast:11434/api/chat").respond(404, json={"error": "model 'x' not found"})
    slow = mock.post("http://slow:11434/api/chat").respond(200)
    _, c = await client_for(mock)
    r = await c.post("/api/chat", json={"model": "llama3"})
    assert r.status_code == 404 and r.json() == {"error": "model 'x' not found"}
    assert not slow.called


async def test_connect_failure_fails_over_to_next_candidate(mock):
    setup_nodes(mock)
    mock.post("http://fast:11434/api/chat").mock(side_effect=httpx.ConnectError("refused"))
    mock.post("http://slow:11434/api/chat").respond(200, content=NDJSON)
    app, c = await client_for(mock)
    r = await c.post("/api/chat", json={"model": "llama3"})
    assert r.headers["x-nexus-node"] == "slow" and r.content == NDJSON
    assert all(s.in_flight == 0 for s in app.state.poller.states.values())


async def test_no_retry_after_bytes_were_sent(mock):
    setup_nodes(mock)

    async def broken():
        yield b'{"response":"a"}\n'
        raise httpx.ReadError("connection lost")

    mock.post("http://fast:11434/api/chat").respond(200, content=broken())
    slow = mock.post("http://slow:11434/api/chat").respond(200, content=NDJSON)
    app, c = await client_for(mock)
    with pytest.raises(httpx.ReadError):
        await c.post("/api/chat", json={"model": "llama3"})
    assert not slow.called
    assert app.state.poller.states["fast"].in_flight == 0


async def test_all_nodes_down_gives_502(mock):
    setup_nodes(mock)
    mock.post("http://fast:11434/api/chat").mock(side_effect=httpx.ConnectError("x"))
    mock.post("http://slow:11434/api/chat").mock(side_effect=httpx.ConnectError("x"))
    _, c = await client_for(mock)
    r = await c.post("/api/chat", json={"model": "llama3"})
    assert r.status_code == 502 and "error" in r.json()


async def test_in_flight_counted_while_streaming(mock):
    setup_nodes(mock)
    seen = []

    async def body():
        seen.append(app.state.poller.states["fast"].in_flight)
        yield b"x"

    mock.post("http://fast:11434/api/chat").respond(200, content=body())
    app, c = await client_for(mock)
    await c.post("/api/chat", json={"model": "llama3"})
    assert seen == [1] and app.state.poller.states["fast"].in_flight == 0


async def test_no_read_timeout_configured(mock):
    app = create_app(make_config(), poll=False)
    # the poller shares the proxy client; its default timeout must not limit reads
    t = app.state.poller.client.timeout
    assert t.read is None and t.connect is not None


async def test_unknown_model_goes_to_highest_priority_healthy(mock):
    setup_nodes(mock)
    mock.post("http://fast:11434/api/chat").respond(404, json={"error": "not found"})
    _, c = await client_for(mock)
    r = await c.post("/api/chat", json={"model": "nope"})
    assert r.headers["x-nexus-node"] == "fast" and r.status_code == 404


# -- aggregation / passthrough / fan-out ---------------------------------------------------------

async def test_tags_merged_and_deduplicated(mock):
    mock_node(mock, "fast", models=("a:latest", "b:latest"))
    mock_node(mock, "slow", models=("b:latest", "c:latest"))
    _, c = await client_for(mock)
    r = await c.get("/api/tags")
    assert [m["name"] for m in r.json()["models"]] == ["a:latest", "b:latest", "c:latest"]
    assert "x-nexus-node" not in r.headers


async def test_tags_skips_dead_node(mock):
    mock_node(mock, "fast", models=("a:latest",))
    mock_node(mock, "slow", ollama=False, agent=False)
    _, c = await client_for(mock)
    assert [m["name"] for m in (await c.get("/api/tags")).json()["models"]] == ["a:latest"]


async def test_ps_and_v1_models(mock):
    setup_nodes(mock, fast={"loaded": {"a:latest": 100}}, slow={"loaded": {"a:latest": 50, "b:latest": 10}})
    mock.get("http://fast:11434/v1/models").respond(json={"object": "list", "data": [{"id": "a"}, {"id": "b"}]})
    mock.get("http://slow:11434/v1/models").respond(json={"object": "list", "data": [{"id": "b"}, {"id": "c"}]})
    _, c = await client_for(mock)
    assert [m["name"] for m in (await c.get("/api/ps")).json()["models"]] == ["a:latest", "b:latest"]
    v1 = (await c.get("/v1/models")).json()
    assert v1["object"] == "list" and [m["id"] for m in v1["data"]] == ["a", "b", "c"]


async def test_root_and_head(mock):
    setup_nodes(mock)
    _, c = await client_for(mock)
    r = await c.get("/")
    assert r.text == "Ollama is running"
    assert (await c.head("/")).status_code == 200


async def test_version_and_unknown_paths_forwarded_to_primary(mock):
    setup_nodes(mock)
    mock.get("http://fast:11434/api/version").respond(json={"version": "0.5.0"})
    mock.delete("http://fast:11434/api/other").respond(204)
    _, c = await client_for(mock)
    r = await c.get("/api/version")
    assert r.json() == {"version": "0.5.0"} and r.headers["x-nexus-node"] == "fast"
    assert (await c.delete("/api/other")).status_code == 204


async def test_passthrough_skips_unhealthy_primary(mock):
    mock_node(mock, "fast", ollama=False, agent=False)
    mock_node(mock, "slow")
    mock.get("http://slow:11434/api/version").respond(json={"version": "1"})
    _, c = await client_for(mock)
    assert (await c.get("/api/version")).headers["x-nexus-node"] == "slow"


async def test_pull_fans_out_to_healthy_nodes_only(mock):
    cfg = make_config()
    mock_node(mock, "fast")
    mock_node(mock, "slow")
    # third node is down
    from nexus_router.config import NodeConfig
    cfg = make_config(nodes=[*cfg.nodes, NodeConfig("dead", "http://dead:11434", None, priority=3)])
    mock_node(mock, "dead", ollama=False, agent=False)
    p_fast = mock.post("http://fast:11434/api/pull").respond(200, content=NDJSON)
    p_slow = mock.post("http://slow:11434/api/pull").respond(200, content=b'{"status":"success"}')
    p_dead = mock.post("http://dead:11434/api/pull").respond(200)
    app, c = await client_for(mock, cfg)
    r = await c.post("/api/pull", json={"model": "x"})
    assert r.content == NDJSON and r.headers["x-nexus-node"] == "fast"
    import asyncio
    await asyncio.sleep(0.05)
    assert p_slow.called and not p_dead.called


async def test_delete_fans_out(mock):
    setup_nodes(mock)
    d1 = mock.delete("http://fast:11434/api/delete").respond(200)
    d2 = mock.delete("http://slow:11434/api/delete").respond(200)
    _, c = await client_for(mock)
    r = await c.request("DELETE", "/api/delete", json={"model": "x"})
    assert r.status_code == 200
    import asyncio
    await asyncio.sleep(0.05)
    assert d1.called and d2.called


# -- router endpoints ------------------------------------------------------------------------------

async def test_health_ok_with_every_node_down(mock):
    mock_node(mock, "fast", ollama=False, agent=False)
    mock_node(mock, "slow", ollama=False, agent=False)
    _, c = await client_for(mock)
    r = await c.get("/router/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_status_reports_nodes_and_decisions(mock):
    setup_nodes(mock, fast={"free_mb": 5000, "loaded": {"llama3:latest": 1000}})
    mock.post("http://fast:11434/api/chat").respond(200, content=b"x")
    _, c = await client_for(mock)
    await c.post("/api/chat", json={"model": "llama3"})
    s = (await c.get("/router/status")).json()
    fast = next(n for n in s["nodes"] if n["name"] == "fast")
    assert fast["healthy"] and fast["effective_free_mb"] == 6000 and fast["loaded_models"] == ["llama3:latest"]
    assert {"busy", "in_flight", "gpus"} <= fast.keys()
    assert s["recent_decisions"][-1]["node"] == "fast" and s["recent_decisions"][-1]["model"] == "llama3"


async def test_routed_request_is_logged_with_model_and_node(mock, caplog):
    setup_nodes(mock)
    mock.post("http://fast:11434/api/chat").respond(200, content=b"x")
    _, c = await client_for(mock)
    with caplog.at_level("INFO", logger="nexus_router"):
        await c.post("/api/chat", json={"model": "llama3"})
    assert any("model=llama3" in r.message and "fast" in r.message for r in caplog.records)
