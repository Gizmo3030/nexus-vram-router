---
id: TASK-10
title: 'CLI entry point: nexus-router'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
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
- [ ] #1 nexus-router --config PATH loads the config and serves on listen.host:listen.port
- [ ] #2 An invalid or missing config exits non-zero and prints the ConfigError message
- [ ] #3 The poller starts with the app and stops cleanly on shutdown
- [ ] #4 Each routed request is logged with the model and the node it went to
<!-- AC:END -->
