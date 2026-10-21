---
id: TASK-8
title: 'Router endpoints: /router/health and /router/status'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
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
- [ ] #1 GET /router/health returns 200 {"status":"ok"} even when every node is down
- [ ] #2 GET /router/status shows per node: health, GPUs, effective free VRAM, loaded models, busy flag and in-flight count, plus recent routing decisions
- [ ] #3 No router-specific fields are added to any Ollama endpoint response
<!-- AC:END -->
