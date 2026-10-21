---
id: TASK-1
title: 'VRAM agent: report GPU memory over HTTP'
status: In Progress
assignee: []
created_date: '2026-10-21T04:12:00Z'
updated_date: '2026-10-21T04:35:00Z'
labels:
  - agent
dependencies: []
references:
  - src/nexus_router/agent.py
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ollama's API only reports VRAM that Ollama itself holds, so it cannot see memory taken by a game. Each GPU machine therefore runs a small agent that the router polls for real GPU memory and utilization. GPU machines run Windows and get this as a single copied file, so it must stay standard-library only, with no imports from the rest of the package, and work on Python 3.10+. Implemented in src/nexus_router/agent.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /vram returns JSON {"gpus": [...]} with index, name, total_mb, used_mb, free_mb and util_percent for every GPU reported by nvidia-smi
- [x] #2 nvidia-smi fields shown as [N/A] or [Not Supported] become null instead of crashing, and GPU names containing commas parse correctly
- [x] #3 With --token set, requests without a matching Authorization: Bearer header get 401
- [x] #4 If nvidia-smi fails, /vram returns 500 with an error message; unknown paths return 404
- [ ] #5 Runs on Windows without opening a console window under pythonw, using only the standard library
- [x] #6 Unit tests cover parse_nvidia_smi (multiple GPUs, [N/A] fields, comma in name) and the 401/404/500 responses
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add tests/test_agent.py: parse_nvidia_smi cases; live HTTP server tests for 200/401/404/500
2. Run pytest
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented in src/nexus_router/agent.py. Verified 2026-10-20: query_gpus() returns correct data from real nvidia-smi on the Linux dev box (RTX 3060 Laptop). Remaining: unit tests, and a run on Windows under pythonw.

2026-10-21: Added tests/test_agent.py (parse + live HTTP 200/401/404/500). Test found names with commas lost their spacing; parse_nvidia_smi now uses rsplit to keep it. Re-verified against real nvidia-smi. AC #5 (Windows/pythonw) still needs a run on a Windows machine, so the task stays In Progress.
<!-- SECTION:NOTES:END -->
