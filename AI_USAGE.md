# AI usage disclosure

Write None if no AI was used. Otherwise record each use:

## Use 1 - Baseline investigation and first repair milestone

- Tool/model: OpenAI Codex assistant.
- Purpose: act as a reviewer for the candidate's work, replace unsafe connection-URL logging, and help structure evidence-based documentation.
- Files or decisions affected: `Dockerfile`, `app/server.py`, `docker-compose.yml`, `nginx/nginx.conf`, `troubleshooting.md`, `decisions.md`, and `security_review.md`.
- What you changed or rejected: the candidate implemented the runtime and proxy fixes and reviewed the generated guidance before use. The assistant directly changed the safe logging statement and drafted the documentation.
- How you independently verified it: ran the 8 supplied unit tests, validated the Compose configuration, rebuilt the stack, inspected container users and processes, tested each upstream from NGINX, tested public endpoints, checked for the removed file and leaked URL schemes, and sampled 20 requests to prove both application instances received traffic.
- Related commit: `fix: restore app and nginx connectivity`.

## Use 2 - Database and cache connectivity review

- Tool/model: OpenAI Codex assistant.
- Purpose: act as a reviewer for the candidate's PostgreSQL, Redis, and local-secret configuration changes and help structure evidence-based documentation.
- Files or decisions affected: `.env.example`, `config/app.env`, `docker-compose.yml`, `troubleshooting.md`, `decisions.md`, and `security_review.md`.
- What you changed or rejected: the candidate implemented and tested the configuration changes. The assistant reviewed the diff and captured outputs, drafted the related documentation, and identified the Gunicorn control-socket warning as unresolved rather than including it in the connectivity claim.
- How you independently verified it: reviewed Compose variable flow without exposing the local password, confirmed the ignored `.env`, checked the supplied unit-test result, and reviewed successful `/ready`, PostgreSQL record creation/listing, Redis increments, container health, and application logs.
- Related commit: `fix: restore database and cache connectivity`.

## Use 3 - Gunicorn control-socket documentation

- Tool/model: OpenAI Codex assistant.
- Purpose: update the documentation from the candidate's Gunicorn change and verification evidence.
- Files or decisions affected: `troubleshooting.md`, `decisions.md`, `security_review.md`, and `AI_USAGE.md` only.
- What you changed or rejected: the assistant updated documentation only. The candidate independently changed the `Dockerfile` and ran the build, health, log, and endpoint verification commands.
- How you independently verified it: reviewed the candidate's one-line Dockerfile diff and timestamped outputs, then confirmed both apps were healthy, the control-socket error was absent from fresh logs, and public `/health` and `/ready` succeeded.
- Related commit: `fix: disable unused gunicorn control socket`.

- Tool/model:
- Purpose:
- Files or decisions affected:
- What you changed or rejected:
- How you independently verified it:
- Related commit:

You may use AI and external resources. You must understand and demonstrate the work.
