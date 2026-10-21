---
id: TASK-11
title: Windows install scripts for the agent
status: In Progress
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
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
- [x] #5 README quick start uses the script instead of the manual steps
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-21: Wrote windows/install-agent.ps1 and uninstall-agent.ps1 (params -Port -Token -Python -InstallDir; replace-not-add task and rule). No PowerShell/Windows on the dev box, so AC 1-4 are unverified: run on a Windows machine, twice, and check Get-ScheduledTask/Get-NetFirewallRule.
<!-- SECTION:NOTES:END -->
