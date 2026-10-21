---
id: TASK-3
title: 'Poller: track live state of every node'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
labels:
  - router
dependencies:
  - TASK-1
  - TASK-2
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Routing has to be decided instantly per request, so node state is gathered in the background and kept in memory: GPU memory and utilization from the agent, loaded models from Ollama /api/ps, pulled models from /api/tags, and health. One slow or offline node must never delay polling of the others or a client request.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each node agent /vram, Ollama /api/ps and /api/tags are polled concurrently every poll_interval_s, sending agent_token when configured
- [x] #2 A node with no successful poll within stale_after_s is unhealthy, and becomes healthy again on the next successful poll
- [x] #3 A node without agent_url is healthy when Ollama answers, with its VRAM recorded as unknown
- [x] #4 An agent returning 500 or unreachable marks VRAM unknown without stopping the poller
- [x] #5 Effective free VRAM = GPU free + VRAM held by Ollama - reserve_mb, with Ollama byte values converted to MiB
- [x] #6 Unit tests with mocked HTTP cover healthy, stale, agent-less and agent-error nodes
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added poller.py: one independent polling loop per node (agent /vram, /api/ps, /api/tags concurrently, bearer token to agents), staleness-based health, agent-less/agent-error nodes with unknown VRAM, effective free VRAM with bytes→MiB conversion. Covered by tests/test_poller.py with respx mocks.
<!-- SECTION:FINAL_SUMMARY:END -->
