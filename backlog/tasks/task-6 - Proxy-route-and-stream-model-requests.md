---
id: TASK-6
title: 'Proxy: route and stream model requests'
status: Done
assignee: []
created_date: '2026-10-21T04:25:00Z'
updated_date: '2026-10-21T04:40:00Z'
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
- [x] #1 POST /api/generate, /api/chat, /api/embed, /api/embeddings, /api/show, /v1/chat/completions, /v1/completions and /v1/embeddings are routed by the model field in the body
- [x] #2 Request bodies are forwarded byte-for-byte; status codes, content types and streamed bodies reach the client unchanged, chunk by chunk
- [x] #3 Proxied requests have no read timeout
- [x] #4 A connect failure before the first response byte retries on the next candidate; nothing is retried once bytes were sent
- [x] #5 Every routed response carries an X-Nexus-Node header naming the node
- [x] #6 A per-node in-flight request count is kept for busy detection
- [x] #7 Tests against mocked nodes cover streaming order, failover and the header
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added proxy.py: model-routed endpoints forward original body bytes, stream raw responses with no read timeout, fail over on connect errors only, add X-Nexus-Node, track in-flight. Verified with respx tests and a live run against a slow chunked fake Ollama (chunks arrived 1s apart).
<!-- SECTION:FINAL_SUMMARY:END -->
