---
id: TASK-12
title: 'Docker: verify image build and healthy container'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
labels:
  - docker
dependencies:
  - TASK-10
  - TASK-8
references:
  - Dockerfile
  - docker-compose.yml
  - .dockerignore
documentation:
  - docs/design-plan.md
priority: medium
type: task
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Dockerfile, .dockerignore and docker-compose.yml were written before the router could run, and the image has never been built (the dev box user could not reach the Docker socket). They need checking once the entry point exists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docker compose build succeeds and the image contains no config.yaml, tests, docs or node_modules
- [ ] #2 docker compose up -d shows the service as healthy and curl http://localhost:11434/ returns "Ollama is running"
- [ ] #3 The container process runs as the non-root nexus user
- [ ] #4 A change to config.yaml takes effect after docker compose restart
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-21: Not verified: the dev user cannot reach /var/run/docker.sock (permission denied), so no build or compose up was possible. Needs a user in the docker group. Entry point now exists; HEALTHCHECK URL /router/health is implemented.
<!-- SECTION:NOTES:END -->
