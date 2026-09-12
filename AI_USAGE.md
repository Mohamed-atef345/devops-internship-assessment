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

## Use 4 - Network-isolation documentation

- Tool/model: OpenAI Codex assistant.
- Purpose: update documentation from the candidate's network-isolation change and verification evidence.
- Files or decisions affected: `troubleshooting.md`, `decisions.md`, `security_review.md`, and `AI_USAGE.md` only.
- What you changed or rejected: the assistant updated documentation only. The candidate independently changed `docker-compose.yml` and ran all Compose, inspection, isolation, and endpoint verification commands.
- How you independently verified it: reviewed the candidate's diff and timestamped outputs, including network membership, absence of dependency host bindings, failed NGINX-to-dependency resolution, successful readiness from both apps, and successful public health/readiness.
- Related commit: `fix: enforce service network isolation`.

## Use 5 - Persistence test guidance and documentation

- Tool/model: OpenAI Codex assistant.
- Purpose: provide commands to test the candidate's PostgreSQL and Redis persistence fix and update the documentation from the resulting evidence.
- Files or decisions affected: `troubleshooting.md`, `decisions.md`, `security_review.md`, and `AI_USAGE.md` only.
- What you changed or rejected: the assistant provided the persistence test commands and updated documentation only. The candidate independently changed `docker-compose.yml`, executed the commands, diagnosed the initially unset proof-title variable, and completed the persistence verification.
- How you independently verified it: reviewed the candidate's Compose diff and timestamped outputs showing the correct mounts and Redis settings, PostgreSQL record creation, Redis counter value before recreation, forced container recreation without volume deletion, the surviving record, the continuing counter, healthy services, and successful readiness.
- Related commit: `fix: persist database and cache data`.

## Use 6 - Availability-hardening review and documentation

- Tool/model: OpenAI Codex assistant.
- Purpose: update documentation from the candidate's evidence.
- Files or decisions affected: `troubleshooting.md`, `decisions.md`, `security_review.md`, and `AI_USAGE.md` only.
- What you changed or rejected: the assistant updated documentation only. The candidate independently changed `docker-compose.yml` and `nginx/nginx.conf`, executed the failure/recovery checks, and supplied the timestamped outputs for review.
- How you independently verified it: reviewed the implementation diff and outputs for NGINX syntax, effective restart/resource values, public health/readiness, NGINX health during an app outage, uninterrupted traffic through the surviving app, and traffic through both apps after recovery.
- Related commit: `fix: harden service availability and failover`.

## Use 7 - Full-stack validation review, fixes and documentation

- Tool/model: OpenAI Codex assistant.
- Purpose: review the candidate's initial `validate.py`, add missing assessment-required behavior, and update the related documentation.
- Files or decisions affected: `validate.py`, `troubleshooting.md`, `decisions.md`, `docs/EVIDENCE_INDEX.md`, and `AI_USAGE.md`.
- What you changed or rejected: the candidate wrote the initial validator. The assistant identified and directly fixed the missing bounded readiness wait, running-only backend discovery, fixed-port behavior, permissive NGINX binding check, missing essential response checks, and unbounded subprocess calls. Optional direct dependency commands, resource checks, and failure injection were deliberately excluded to keep validation minimal.
- How you independently verified it: the candidate ran the final validator against the healthy stack and supplied output showing every check passed, both app identities were observed, a PostgreSQL record was created/retrieved, Redis increased from 15 to 16, and the final result passed. The assistant also ran Python compilation, a whitespace/diff check, a healthy exit-code test, and a harmless unused-port test that failed within its two-second bound with exit 1.
- Documentation assistance: the assistant drafted the validation entry in `troubleshooting.md`, the validation decision in `decisions.md`, this disclosure, and the pending validation row in `docs/EVIDENCE_INDEX.md`; the candidate reviewed and retained responsibility for the submitted content.
- Related commit: `test: add bounded full-stack validation` (the commit containing `validate.py` and these documentation updates).

- Tool/model:
- Purpose:
- Files or decisions affected:
- What you changed or rejected:
- How you independently verified it:
- Related commit:

You may use AI and external resources. You must understand and demonstrate the work.
