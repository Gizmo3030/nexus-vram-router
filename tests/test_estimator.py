from nexus_router.config import EstimateConfig
from nexus_router.estimator import bytes_to_mb, estimate_mb, normalize_model

MIB = 1024 * 1024
EST = EstimateConfig(overhead_factor=1.2, overhead_mb=512)


def test_normalize_adds_latest():
    assert normalize_model("llama3") == "llama3:latest"
    assert normalize_model("llama3:latest") == "llama3:latest"
    assert normalize_model("llama3:8b") == "llama3:8b"
    assert normalize_model("library/llama3") == "library/llama3:latest"


def test_normalize_ignores_registry_port():
    assert normalize_model("localhost:5000/m") == "localhost:5000/m:latest"
    assert normalize_model("localhost:5000/m:q4") == "localhost:5000/m:q4"


def test_bytes_to_mb_rounds_up():
    assert bytes_to_mb(MIB) == 1
    assert bytes_to_mb(MIB + 1) == 2
    assert bytes_to_mb(0) == 0


def test_loaded_model_uses_size_vram_and_fits():
    e = estimate_mb("m:latest", {"m:latest": 4000 * MIB}, {"m:latest": 9000 * MIB}, EST)
    assert (e.mb, e.loaded) == (4000, True)


def test_not_loaded_uses_file_size_times_factor_plus_overhead():
    e = estimate_mb("m:latest", {}, {"m:latest": 1000 * MIB}, EST)
    assert (e.mb, e.loaded) == (1200 + 512, False)


def test_unknown_model():
    assert estimate_mb("x:latest", {}, {}, EST).mb is None
