"""VRAM agent: a tiny HTTP service that reports this machine's GPU memory.

Standard library only, so this single file can be copied to a GPU machine and
run with any Python 3.10+ install:

    python agent.py --port 11500 [--token SECRET]

GET /vram  ->  {"gpus": [{"index": 0, "name": "...", "total_mb": ..., "used_mb": ...,
                          "free_mb": ..., "util_percent": ...}]}
"""

from __future__ import annotations

import argparse
import hmac
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUERY = "index,name,memory.total,memory.used,memory.free,utilization.gpu"


def _int_or_none(value: str) -> int | None:
    try:
        return int(float(value))
    except ValueError:
        # nvidia-smi prints "[N/A]" or "[Not Supported]" for some fields.
        return None


def parse_nvidia_smi(output: str) -> list[dict]:
    gpus = []
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        # GPU names can contain commas, so take the numeric fields from the end.
        index, *name_parts = parts[:-4]
        total, used, free, util = (_int_or_none(p) for p in parts[-4:])
        gpus.append(
            {
                "index": _int_or_none(index),
                "name": ",".join(name_parts).strip(),
                "total_mb": total,
                "used_mb": used,
                "free_mb": free,
                "util_percent": util,
            }
        )
    return gpus


def query_gpus(nvidia_smi: str = "nvidia-smi") -> list[dict]:
    flags = 0
    if sys.platform == "win32":
        # Don't flash a console window when running under pythonw.
        flags = subprocess.CREATE_NO_WINDOW
    out = subprocess.run(
        [nvidia_smi, f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        creationflags=flags,
    ).stdout
    return parse_nvidia_smi(out)


def make_handler(token: str | None, nvidia_smi: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "nexus-agent"

        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if token is not None:
                given = self.headers.get("Authorization", "").removeprefix("Bearer ")
                if not hmac.compare_digest(given, token):
                    self._send(401, {"error": "unauthorized"})
                    return
            if self.path.split("?")[0] != "/vram":
                self._send(404, {"error": "not found"})
                return
            try:
                self._send(200, {"gpus": query_gpus(nvidia_smi)})
            except Exception as e:  # report nvidia-smi failures to the router
                self._send(500, {"error": f"nvidia-smi failed: {e}"})

        def log_message(self, format: str, *args) -> None:
            pass  # the router polls every few seconds; keep the console quiet

    return Handler


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Report GPU VRAM over HTTP for nexus-router.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=11500)
    p.add_argument("--token", default=None, help="require 'Authorization: Bearer TOKEN'")
    p.add_argument("--nvidia-smi", default="nvidia-smi", help="path to nvidia-smi")
    args = p.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.token, args.nvidia_smi))
    print(f"nexus-agent listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
