---
id: TASK-3
title: 'Poller: track live state of every node'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
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
- [ ] #1 Each node agent /vram, Ollama /api/ps and /api/tags are polled concurrently every poll_interval_s, sending agent_token when configured
- [ ] #2 A node with no successful poll within stale_after_s is unhealthy, and becomes healthy again on the next successful poll
- [ ] #3 A node without agent_url is healthy when Ollama answers, with its VRAM recorded as unknown
- [ ] #4 An agent returning 500 or unreachable marks VRAM unknown without stopping the poller
- [ ] #5 Effective free VRAM = GPU free + VRAM held by Ollama - reserve_mb, with Ollama byte values converted to MiB
- [ ] #6 Unit tests with mocked HTTP cover healthy, stale, agent-less and agent-error nodes
<!-- AC:END -->
