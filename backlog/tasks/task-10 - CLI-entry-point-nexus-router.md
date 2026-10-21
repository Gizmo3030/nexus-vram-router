---
id: TASK-10
title: 'CLI entry point: nexus-router'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
labels:
  - router
  - docker
dependencies:
  - TASK-6
  - TASK-8
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pyproject.toml declares nexus-router = nexus_router.main:router_main and the Docker image ENTRYPOINT runs it with --config /config/config.yaml, so neither the CLI nor the container can start until it exists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 nexus-router --config PATH loads the config and serves on listen.host:listen.port
- [x] #2 An invalid or missing config exits non-zero and prints the ConfigError message
- [x] #3 The poller starts with the app and stops cleanly on shutdown
- [x] #4 Each routed request is logged with the model and the node it went to
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added main.py router_main: loads config, prints ConfigError/OSError/YAML errors and exits 1, runs uvicorn on listen host/port, poller started/stopped via lifespan, routed requests logged with model and node. tests/test_main.py plus live run.
<!-- SECTION:FINAL_SUMMARY:END -->
