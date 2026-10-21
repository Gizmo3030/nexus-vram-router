import httpx
import respx

from conftest import MIB, make_config, mock_node
from nexus_router.config import BusyConfig, NodeConfig
from nexus_router.poller import Poller, effective_free_mb


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


async def make(cfg=None):
    clock = Clock()
    p = Poller(cfg or make_config(), httpx.AsyncClient(), clock)
    return p, clock


def test_effective_free_adds_ollama_held_vram_and_subtracts_reserve():
    gpus = [{"free_mb": 1000}]
    assert effective_free_mb(gpus, {"m:latest": 3000 * MIB}, 512) == 1000 + 3000 - 512
    assert effective_free_mb(gpus, {}, 5000) == 0
    assert effective_free_mb(None, {}, 0) is None
    assert effective_free_mb([{"free_mb": None}], {}, 0) is None
    assert effective_free_mb([{"free_mb": 100}, {"free_mb": 200}], {}, 0) == 300


@respx.mock
async def test_healthy_node_state():
    mock_node(respx, "fast", free_mb=5000, loaded={"llama3:latest": 2000})
    mock_node(respx, "slow", free_mb=100)
    p, _ = await make()
    await p.poll_all()
    fast = p.view(p.states["fast"])
    assert fast.healthy and fast.free_mb == 7000
    assert "llama3:latest" in fast.models and "llama3:latest" in fast.loaded


@respx.mock
async def test_token_sent_to_agent():
    mock_node(respx, "fast")
    mock_node(respx, "slow")
    p, _ = await make(make_config(agent_token="tok"))
    await p.poll_all()
    agent_calls = [c for c in respx.calls if c.request.url.port == 11500]
    assert agent_calls and all(c.request.headers["authorization"] == "Bearer tok" for c in agent_calls)


@respx.mock
async def test_node_goes_stale_then_recovers():
    mock_node(respx, "fast")
    mock_node(respx, "slow", ollama=False, agent=False)
    p, clock = await make()
    await p.poll_all()
    assert p.view(p.states["fast"]).healthy and not p.view(p.states["slow"]).healthy
    clock.now += 11  # stale_after_s defaults to 10
    assert not p.view(p.states["fast"]).healthy
    await p.poll_all()
    assert p.view(p.states["fast"]).healthy


@respx.mock
async def test_node_without_agent_is_healthy_with_unknown_vram():
    mock_node(respx, "solo", agent=False)
    cfg = make_config(nodes=[NodeConfig("solo", "http://solo:11434")])
    p, _ = await make(cfg)
    await p.poll_all()
    v = p.view(p.states["solo"])
    assert v.healthy and v.free_mb is None


@respx.mock
async def test_agent_error_marks_vram_unknown_but_keeps_polling():
    mock_node(respx, "fast", agent="error")
    mock_node(respx, "slow")
    p, _ = await make()
    await p.poll_all()
    fast = p.view(p.states["fast"])
    assert fast.healthy and fast.free_mb is None
    assert p.view(p.states["slow"]).free_mb == 10000


@respx.mock
async def test_unreachable_agent_marks_vram_unknown():
    mock_node(respx, "fast", agent=False)
    respx.get("http://fast:11500/vram").mock(side_effect=httpx.ConnectError("x"))
    mock_node(respx, "slow")
    p, _ = await make()
    await p.poll_all()
    assert p.view(p.states["fast"]).free_mb is None and p.view(p.states["fast"]).healthy


# -- busy detection ---------------------------------------------------------------------------

def set_util(util):
    respx.get("http://fast:11500/vram").respond(json={"gpus": [{"free_mb": 1000, "util_percent": util}]})


@respx.mock
async def test_busy_after_consecutive_high_polls_and_one_low_poll_clears():
    mock_node(respx, "fast")
    mock_node(respx, "slow")
    p, _ = await make()
    st = p.states["fast"]
    set_util(95)
    await p.poll_node(st); await p.poll_node(st)
    assert not st.busy
    await p.poll_node(st)
    assert st.busy
    set_util(85)  # at the threshold is not above it
    await p.poll_node(st)
    assert not st.busy


@respx.mock
async def test_high_util_while_router_has_requests_in_flight_is_not_busy():
    mock_node(respx, "fast")
    mock_node(respx, "slow")
    p, _ = await make()
    st = p.states["fast"]
    st.in_flight = 1
    set_util(99)
    for _ in range(5):
        await p.poll_node(st)
    assert not st.busy


@respx.mock
async def test_busy_check_can_be_disabled():
    mock_node(respx, "fast")
    mock_node(respx, "slow")
    p, _ = await make(make_config(busy=BusyConfig(gpu_util_percent=None)))
    st = p.states["fast"]
    set_util(100)
    for _ in range(5):
        await p.poll_node(st)
    assert not st.busy
