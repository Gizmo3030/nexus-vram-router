"""Tests for the VRAM agent: nvidia-smi parsing and the HTTP responses."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from nexus_router import agent
from nexus_router.agent import make_handler, parse_nvidia_smi

TWO_GPUS = """\
0, NVIDIA GeForce RTX 4080 SUPER, 16376, 2048, 14000, 7
1, NVIDIA GeForce RTX 2070 SUPER, 8192, 100, 8000, 0
"""


def test_parse_multiple_gpus():
    assert parse_nvidia_smi(TWO_GPUS) == [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 4080 SUPER",
            "total_mb": 16376,
            "used_mb": 2048,
            "free_mb": 14000,
            "util_percent": 7,
        },
        {
            "index": 1,
            "name": "NVIDIA GeForce RTX 2070 SUPER",
            "total_mb": 8192,
            "used_mb": 100,
            "free_mb": 8000,
            "util_percent": 0,
        },
    ]


@pytest.mark.parametrize("marker", ["[N/A]", "[Not Supported]"])
def test_parse_unavailable_fields_become_none(marker):
    [gpu] = parse_nvidia_smi(f"0, Some GPU, 8192, {marker}, {marker}, {marker}\n")
    assert gpu["total_mb"] == 8192
    assert gpu["used_mb"] is None
    assert gpu["free_mb"] is None
    assert gpu["util_percent"] is None


def test_parse_name_with_commas():
    [gpu] = parse_nvidia_smi("0, NVIDIA RTX A2000, 12GB, Laptop, 12288, 500, 11788, 3\n")
    assert gpu["name"] == "NVIDIA RTX A2000, 12GB, Laptop"
    assert (gpu["total_mb"], gpu["used_mb"], gpu["free_mb"], gpu["util_percent"]) == (12288, 500, 11788, 3)


def test_parse_skips_blank_and_short_lines():
    assert parse_nvidia_smi("") == []
    assert parse_nvidia_smi("\ngarbage line\n") == []


@pytest.fixture
def serve(monkeypatch):
    """Start the agent on an ephemeral port; returns a function that builds the server's URL."""
    servers: list[ThreadingHTTPServer] = []

    def start(token: str | None = None, gpus=None, error: Exception | None = None) -> str:
        def fake_query(_nvidia_smi: str):
            if error is not None:
                raise error
            return gpus if gpus is not None else parse_nvidia_smi(TWO_GPUS)

        monkeypatch.setattr(agent, "query_gpus", fake_query)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(token, "nvidia-smi"))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for s in servers:
        s.shutdown()
        s.server_close()


def get(url: str, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_vram_returns_gpus(serve):
    status, body = get(serve() + "/vram")
    assert status == 200
    assert [g["index"] for g in body["gpus"]] == [0, 1]
    assert body["gpus"][0]["free_mb"] == 14000


def test_vram_ignores_query_string(serve):
    status, _ = get(serve() + "/vram?x=1")
    assert status == 200


def test_unknown_path_is_404(serve):
    status, body = get(serve() + "/nope")
    assert status == 404
    assert "error" in body


def test_nvidia_smi_failure_is_500(serve):
    status, body = get(serve(error=RuntimeError("boom")) + "/vram")
    assert status == 500
    assert "boom" in body["error"]


def test_token_required(serve):
    url = serve(token="s3cret") + "/vram"
    assert get(url)[0] == 401
    assert get(url, token="wrong")[0] == 401
    assert get(url, token="s3cret")[0] == 200


def test_token_checked_before_path(serve):
    # Unauthenticated callers must not learn which paths exist.
    assert get(serve(token="s3cret") + "/nope")[0] == 401
