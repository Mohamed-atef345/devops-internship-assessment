# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision 1 - Use Gunicorn with an unprivileged application user

- Choice: run `app.server:create_app()` with Gunicorn, two workers, and the existing numeric `app` user instead of starting Flask's development server as root.
- Why: Gunicorn is already pinned in the project dependencies, supports a production-style multi-process runtime, and the application does not need root privileges to listen on port 8080.
- Alternative: keep `python -m app.server`, which is simpler but uses Flask's development server and previously ran as root.
- Trade-off: two workers consume more memory than one process, and worker count is a starting value rather than a universally optimal setting.
- Evidence / commit: process inspection showed UID 10001, a Gunicorn master, and two workers; `fix: restore app and nginx connectivity`.
- Production improvement: tune worker count and timeouts from measured traffic and memory use, add graceful-shutdown testing, and consider a read-only root filesystem where practical.

## Decision 2 - Keep liveness independent from dependency readiness

- Choice: use `/health` for the app container health check and retain `/ready` for checking PostgreSQL and Redis availability.
- Why: a reachable application process should remain healthy even when a dependency is temporarily unavailable. This separation makes the cause of an outage visible and avoids restarting a functioning app for an external dependency failure.
- Alternative: use `/ready` as the Docker health check, which would mark the app unhealthy whenever PostgreSQL or Redis is unavailable.
- Trade-off: an app can be container-healthy while dependency-backed endpoints return 503, so readiness must be checked separately in validation and monitoring.
- Evidence / commit: both app containers became healthy through `/health` while `/ready` accurately reported unavailable dependencies; `fix: restore app and nginx connectivity`.
- Production improvement: use an orchestrator that treats liveness and readiness as separate probes and removes unready instances from service without unnecessary restarts.

## Decision 3 - Inject the lab credential from an ignored local environment file

- Choice: keep the synthetic PostgreSQL password in the ignored root `.env`, provide only a safe placeholder in `.env.example`, and use Compose interpolation to supply consistent connection settings to PostgreSQL and both app instances.
- Why: one local source prevents password mismatches while keeping the active value out of the current image, source files, and Compose definition.
- Alternative: retain the tracked `config/app.env` and duplicate the password in the PostgreSQL service, which caused configuration drift and exposed the value in the repository.
- Trade-off: Compose environment variables remain visible to users with Docker inspection access, and passwords containing URL-reserved characters would require correct URL encoding.
- Evidence / commit: `.env` is ignored, `config/app.env` is removed from the current tree, and real `/ready`, `/records`, and `/counter` operations succeed; `fix: restore database and cache connectivity`.
- Production improvement: use a deployment secret store or mounted secret with access controls and rotation instead of a local environment file.

## Decision 4 - Disable the unused Gunicorn control socket

- Choice: pass `--no-control-socket` to Gunicorn while retaining the no-home, unprivileged `app` user.
- Why: the assessment does not use Gunicorn's runtime control interface, and its default socket path caused a permission error below `/home/app`.
- Alternative: create a writable home or runtime directory for the socket, which would add storage and permissions for an interface the service does not need.
- Trade-off: runtime management through `gunicornc` is unavailable; normal process lifecycle remains managed by Docker Compose.
- Evidence / commit: both app startup logs are free of the control-socket error, both containers are healthy, and public liveness/readiness remain HTTP 200; `fix: disable unused gunicorn control socket`.
- Production improvement: if runtime control is later required, configure an explicit protected socket path and ownership rather than relying on a default home-directory fallback.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.
