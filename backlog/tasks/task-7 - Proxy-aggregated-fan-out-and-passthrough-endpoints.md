---
id: TASK-7
title: 'Proxy: aggregated, fan-out and passthrough endpoints'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - router
dependencies:
  - TASK-6
documentation:
  - docs/design-plan.md
priority: medium
type: feature
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apps list and manage models through the same endpoint, so they must see every node as one server, and pulling a model should put it on every machine so any node can serve it. Everything else Ollama exposes must still work through the router.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GET /api/tags, /api/ps and /v1/models combine the results of all healthy nodes, de-duplicated by model name, in the normal Ollama response format
- [ ] #2 POST /api/pull and DELETE /api/delete run on every healthy node; the client sees the primary node streamed progress and the other results are logged
- [ ] #3 GET / returns "Ollama is running" and HEAD / succeeds
- [ ] #4 GET /api/version and any other path are forwarded to the highest-priority healthy node
- [ ] #5 Tests cover aggregation with overlapping models, fan-out with one node down, and passthrough
<!-- AC:END -->
