---
id: TASK-11
title: Windows install scripts for the agent
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - windows
  - agent
dependencies:
  - TASK-1
documentation:
  - docs/design-plan.md
priority: medium
type: feature
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The GPU machines are Windows PCs. Today the agent has to be started by hand and the firewall opened manually, so it stops on every reboot and setting up a new machine is error-prone.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 windows/install-agent.ps1 installs agent.py to a fixed location, adds an inbound TCP rule for the agent port on the Private profile, and registers a Scheduled Task that starts it with pythonw at boot
- [ ] #2 Port and token can be passed as script parameters
- [ ] #3 Running the installer twice leaves one task and one firewall rule
- [ ] #4 windows/uninstall-agent.ps1 removes the task, the firewall rule and the installed files
- [ ] #5 README quick start uses the script instead of the manual steps
<!-- AC:END -->
