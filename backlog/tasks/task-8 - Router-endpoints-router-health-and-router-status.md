---
id: TASK-8
title: 'Router endpoints: /router/health and /router/status'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
labels:
  - router
dependencies:
  - TASK-3
  - TASK-6
documentation:
  - docs/design-plan.md
priority: medium
type: feature
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Docker healthcheck needs an endpoint showing the router process is alive that does not depend on any GPU node being up. Debugging routing needs a view of what the router currently believes about each node and why it made recent decisions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /router/health returns 200 {"status":"ok"} even when every node is down
- [x] #2 GET /router/status shows per node: health, GPUs, effective free VRAM, loaded models, busy flag and in-flight count, plus recent routing decisions
- [x] #3 No router-specific fields are added to any Ollama endpoint response
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added /router/health (independent of nodes) and /router/status (nodes, GPUs, free VRAM, loaded models, busy, in-flight, recent decisions). Tested with all nodes down.
<!-- SECTION:FINAL_SUMMARY:END -->
