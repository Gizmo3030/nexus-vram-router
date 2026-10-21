"""CLI entry point: `nexus-router --config config.yaml`."""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn
import yaml

from .config import ConfigError, load_config
from .proxy import create_app


def router_main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Ollama-compatible router that picks a GPU node per request.")
    p.add_argument("--config", default="config.yaml", help="path to the YAML config (default: config.yaml)")
    args = p.parse_args(argv)

    try:
        config = load_config(args.config)
    except (ConfigError, OSError, yaml.YAMLError) as e:
        print(f"nexus-router: invalid config {args.config}: {e}", file=sys.stderr)
        raise SystemExit(1) from None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per poll is just noise
    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    router_main()
