---
id: TASK-9
title: 'Busy detection: skip nodes under sustained GPU load'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
labels:
  - router
dependencies:
  - TASK-3
  - TASK-5
  - TASK-6
documentation:
  - docs/design-plan.md
priority: medium
type: feature
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Some games use a lot of GPU compute but little VRAM, so free VRAM alone would still send AI work to a GPU that is in use for gaming. A node counts as busy only while the router has no requests running on it, so the router own traffic never marks a node busy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A node is busy when util_percent stays above busy.gpu_util_percent for busy.consecutive_polls polls in a row while its in-flight count is zero
- [x] #2 One poll below the threshold clears busy
- [x] #3 busy.gpu_util_percent: null disables the check
- [x] #4 Behavior when every node that has the model is busy is decided and recorded in docs/design-plan.md
- [x] #5 Unit tests cover the threshold, reset, disabled and router-own-load cases
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Busy detection lives in Poller._update_busy: util above threshold for consecutive polls with zero in-flight; reset on one low poll; null disables. All-busy behavior documented in docs/design-plan.md. Tests in tests/test_poller.py.
<!-- SECTION:FINAL_SUMMARY:END -->
