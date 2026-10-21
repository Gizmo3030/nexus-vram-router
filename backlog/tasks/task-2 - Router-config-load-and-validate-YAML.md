---
id: TASK-2
title: 'Router config: load and validate YAML'
status: In Progress
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - router
  - config
dependencies: []
references:
  - src/nexus_router/config.py
  - config.example.yaml
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The router is driven by one YAML file (nodes, priorities, VRAM reserves, polling, estimate and busy settings) that is mounted into the Docker container. Bad config must fail fast at startup with a message naming the field, instead of surfacing later as wrong routing. Implemented in src/nexus_router/config.py; config.example.yaml documents every key and README has the reference table.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 config.example.yaml loads and every key defaults to the value documented in README
- [ ] #2 Missing nodes, a node without name or ollama_url, and duplicate node names raise ConfigError naming the problem
- [ ] #3 Trailing slashes on ollama_url and agent_url are stripped
- [ ] #4 Nodes without an explicit priority are ordered by their position in the file
- [ ] #5 Unit tests cover the defaults and every error case
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented in src/nexus_router/config.py. Verified 2026-10-20: config.example.yaml loads via load_config() with the expected defaults. Remaining: unit tests.
<!-- SECTION:NOTES:END -->
