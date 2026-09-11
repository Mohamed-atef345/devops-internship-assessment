# AI usage disclosure

Write None if no AI was used. Otherwise record each use:

## Use 1 - Baseline investigation and first repair milestone

- Tool/model: OpenAI Codex assistant.
- Purpose: act as a reviewer for the candidate's work, replace unsafe connection-URL logging, and help structure evidence-based documentation.
- Files or decisions affected: `Dockerfile`, `app/server.py`, `docker-compose.yml`, `nginx/nginx.conf`, `troubleshooting.md`, `decisions.md`, and `security_review.md`.
- What you changed or rejected: the candidate implemented the runtime and proxy fixes and reviewed the generated guidance before use. The assistant directly changed the safe logging statement and drafted the documentation.
- How you independently verified it: ran the supplied 8 test suites, validated the Compose configuration, rebuilt the stack, inspected container users and processes, tested each upstream from NGINX, tested public endpoints, checked for the removed file and leaked URL schemes, and sampled 20 requests to prove both application instances received traffic.
- Related commit: `fix: restore app and nginx connectivity`.

- Tool/model:
- Purpose:
- Files or decisions affected:
- What you changed or rejected:
- How you independently verified it:
- Related commit:

You may use AI and external resources. You must understand and demonstrate the work.
