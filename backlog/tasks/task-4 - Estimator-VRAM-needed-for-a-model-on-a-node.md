---
id: TASK-4
title: 'Estimator: VRAM needed for a model on a node'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - router
dependencies:
  - TASK-3
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
To know whether a model fits on a node before sending it there, the router needs the VRAM the model will take. Ollama does not expose that ahead of loading, so it is estimated from the model file size - unless the model is already loaded on that node, where its real footprint is known.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A model already loaded on the node uses its size_vram from /api/ps and counts as fitting there
- [ ] #2 Otherwise the estimate is the /api/tags file size x estimate.overhead_factor + estimate.overhead_mb, in MiB
- [ ] #3 Model names are normalized so llama3 and llama3:latest match
- [ ] #4 Unit tests cover loaded, not loaded, tag normalization and byte-to-MiB conversion
<!-- AC:END -->
