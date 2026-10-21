---
id: TASK-4
title: 'Estimator: VRAM needed for a model on a node'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
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
- [x] #1 A model already loaded on the node uses its size_vram from /api/ps and counts as fitting there
- [x] #2 Otherwise the estimate is the /api/tags file size x estimate.overhead_factor + estimate.overhead_mb, in MiB
- [x] #3 Model names are normalized so llama3 and llama3:latest match
- [x] #4 Unit tests cover loaded, not loaded, tag normalization and byte-to-MiB conversion
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added estimator.py (normalize_model, bytes_to_mb, estimate_mb): loaded models use size_vram, otherwise tags size x factor + overhead in MiB. tests/test_estimator.py.
<!-- SECTION:FINAL_SUMMARY:END -->
