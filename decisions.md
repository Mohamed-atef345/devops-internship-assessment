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

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.
