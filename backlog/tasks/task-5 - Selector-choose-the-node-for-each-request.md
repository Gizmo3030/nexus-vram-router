---
id: TASK-5
title: 'Selector: choose the node for each request'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - router
dependencies:
  - TASK-3
  - TASK-4
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The core routing policy: use the fastest GPU (lowest priority number) whenever the model fits, and fall back to a slower machine when, for example, a game is holding the RTX 4080 VRAM. It must be pure functions so every case can be unit tested, and must work for any number of nodes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Among healthy, not-busy nodes that have the model, the first in priority order where it fits is chosen
- [ ] #2 If it fits nowhere, the candidate with the most effective free VRAM is chosen; nodes with unknown VRAM rank after all measured nodes
- [ ] #3 If no node has the model, the highest-priority healthy node is chosen so Ollama returns its own error
- [ ] #4 The decision includes the ordered remaining candidates for failover
- [ ] #5 selector.py does no I/O, reads no clock and keeps no global state
- [ ] #6 Unit tests cover: 4080 has room; 4080 full from gaming so 2070 is chosen; model already loaded; nothing fits; unhealthy node; busy node; agent-less node; three or more nodes
<!-- AC:END -->
