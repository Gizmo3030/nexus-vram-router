import pytest

from nexus_router.config import EstimateConfig
from nexus_router.selector import NodeView, select

MIB = 1024 * 1024
EST = EstimateConfig(overhead_factor=1.0, overhead_mb=0)
M = "llama3:latest"


def node(name, priority, free=None, models=(M,), loaded=None, healthy=True, busy=False, size_mb=6000):
    return NodeView(name, priority, healthy, busy, free, {m: size_mb * MIB for m in models},
                    {k: v * MIB for k, v in (loaded or {}).items()})


def pick(nodes, model="llama3"):
    return select(nodes, model, EST)


def test_fastest_node_with_room_wins():
    d = pick([node("slow", 2, 7000), node("fast", 1, 15000)])
    assert d.node == "fast" and d.candidates == ("fast", "slow")


def test_falls_back_when_fast_node_is_full_from_gaming():
    d = pick([node("fast", 1, 2000), node("slow", 2, 7000)])
    assert d.candidates == ("slow", "fast")
    assert d.reason == "fits"


def test_already_loaded_counts_as_fitting_even_with_little_free():
    d = pick([node("fast", 1, 100, loaded={M: 6000}), node("slow", 2, 7000)])
    assert d.node == "fast" and d.reason == "model already loaded"


def test_nothing_fits_picks_most_free():
    d = pick([node("a", 1, 1000), node("b", 2, 4000), node("c", 3, 2000)])
    assert d.candidates == ("b", "c", "a")
    assert "most free" in d.reason


def test_unknown_vram_never_fits_and_ranks_after_measured():
    d = pick([node("noagent", 1, None), node("a", 2, 1000)])
    assert d.candidates == ("a", "noagent")
    d = pick([node("noagent", 1, None), node("a", 2, 9000)])
    assert d.node == "a"


def test_unhealthy_node_excluded():
    d = pick([node("fast", 1, 15000, healthy=False), node("slow", 2, 7000)])
    assert d.candidates == ("slow",)


def test_busy_node_ranked_last_but_kept_for_failover():
    d = pick([node("fast", 1, 15000, busy=True), node("slow", 2, 7000)])
    assert d.candidates == ("slow", "fast")


def test_all_busy_still_routes_to_best_busy_node():
    d = pick([node("fast", 1, 15000, busy=True), node("slow", 2, 7000, busy=True)])
    assert d.candidates == ("fast", "slow")
    assert d.reason == "every node with the model is busy"


def test_nodes_without_the_model_are_skipped():
    d = pick([node("fast", 1, 15000, models=()), node("slow", 2, 7000)])
    assert d.candidates == ("slow",)


def test_no_node_has_model_goes_to_highest_priority_healthy():
    d = pick([node("a", 1, 1000, models=(), healthy=False), node("b", 2, 1, models=()), node("c", 3, 9, models=())])
    assert d.candidates == ("b", "c")
    assert d.reason == "no node has the model"


def test_no_model_in_request():
    assert select([node("b", 2), node("a", 1)], None, EST).candidates == ("a", "b")


def test_no_healthy_nodes_returns_all_by_priority():
    d = pick([node("b", 2, healthy=False), node("a", 1, healthy=False)])
    assert d.candidates == ("a", "b")


def test_three_nodes_mixed():
    d = pick([
        node("a", 1, 500),
        node("b", 2, 9000, busy=True),
        node("c", 3, 6500),
        node("d", 4, 20000),
    ])
    assert d.candidates == ("c", "d", "a", "b")


def test_tag_normalization_matches_latest():
    assert pick([node("a", 1, 9000)], "llama3").node == "a"
    assert pick([node("a", 1, 9000)], "llama3:latest").node == "a"


def test_estimate_overhead_applies():
    est = EstimateConfig(overhead_factor=1.2, overhead_mb=512)  # 6000 -> 7712
    nodes = [node("a", 1, 7000), node("b", 2, 8000)]
    assert select(nodes, "llama3", est).node == "b"


@pytest.mark.parametrize("n", [1, 5, 20])
def test_any_number_of_nodes(n):
    nodes = [node(f"n{i}", i, 100 if i < n - 1 else 9000) for i in range(n)]
    assert pick(nodes).node == f"n{n - 1}"
