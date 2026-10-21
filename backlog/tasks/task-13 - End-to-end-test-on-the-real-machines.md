---
id: TASK-13
title: End-to-end test on the real machines
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - e2e
dependencies:
  - TASK-12
  - TASK-11
  - TASK-9
  - TASK-7
documentation:
  - docs/design-plan.md
priority: medium
type: task
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The point of the project is that AI requests move off the gaming PC while a game runs and come back when it ends. That can only be confirmed on the real RTX 4080 Super and RTX 2070 Super Windows machines with the router running in Docker.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the 4080 idle, a chat request is served by the 4080 node (X-Nexus-Node)
- [ ] #2 With a game running on the 4080, the same request is served by the 2070 node
- [ ] #3 After the game closes, requests go back to the 4080 within a few poll intervals
- [ ] #4 An app such as Open WebUI pointed at the router lists models from both machines and streams chat normally
- [ ] #5 Turning one PC off mid-session leaves the router serving from the other
<!-- AC:END -->
