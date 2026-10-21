---
id: TASK-6
title: 'Proxy: route and stream model requests'
status: To Do
assignee: []
created_date: '2026-10-21T04:25:00Z'
labels:
  - router
dependencies:
  - TASK-5
documentation:
  - docs/design-plan.md
priority: high
type: feature
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apps must not be able to tell the router apart from a real Ollama server. Model requests go to the node the selector picks and the response is streamed back unchanged, including slow model loads and streamed NDJSON (/api/*) and SSE (/v1/*) output.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POST /api/generate, /api/chat, /api/embed, /api/embeddings, /api/show, /v1/chat/completions, /v1/completions and /v1/embeddings are routed by the model field in the body
- [ ] #2 Request bodies are forwarded byte-for-byte; status codes, content types and streamed bodies reach the client unchanged, chunk by chunk
- [ ] #3 Proxied requests have no read timeout
- [ ] #4 A connect failure before the first response byte retries on the next candidate; nothing is retried once bytes were sent
- [ ] #5 Every routed response carries an X-Nexus-Node header naming the node
- [ ] #6 A per-node in-flight request count is kept for busy detection
- [ ] #7 Tests against mocked nodes cover streaming order, failover and the header
<!-- AC:END -->
