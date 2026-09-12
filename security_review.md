# Security and production-readiness review

Record at least 8 concrete risks or improvements relevant to your final solution.
This is a review requirement, not the number of hidden faults.

## Finding 1 - Root process and development server

- Risk and evidence: the supplied application container ran Flask's development server as root. Runtime inspection showed an empty configured user and the Flask development-server warning.
- Impact: an application compromise would have unnecessary privileges inside the container, and the development server is not an appropriate production runtime.
- Implemented fix / commit: run the image as numeric UID 10001 and use Gunicorn with two workers; `fix: restore app and nginx connectivity`.
- Production follow-up: assess dropped Linux capabilities, a read-only root filesystem, and worker/time-out tuning against the deployment environment.
- How to verify: inspect `.Config.User` and use `docker top` to confirm the numeric user, Gunicorn master, and worker processes.

## Finding 2 - Connection configuration exposed through image and logs

- Risk and evidence: the supplied Dockerfile copied `config/app.env` into the image, and direct execution of `app/server.py` logged complete database and Redis URLs. A connection URL may contain credentials and internal topology.
- Impact: anyone with access to the image or logs could recover sensitive connection details.
- Implemented fix / commit: stop copying `config/app.env` into the image and log only booleans indicating whether `DATABASE_URL` and `REDIS_URL` are configured; `fix: restore app and nginx connectivity`.
- Production follow-up: use the deployment platform's secret mechanism instead of environment-variable injection, rotate any value that has been exposed, and restrict access to images and logs. The tracked runtime file is removed from the current project tree in the database/cache connectivity change.
- How to verify: assert that `/srv/app.env` is absent in a running app container and scan fresh app logs for PostgreSQL and Redis URL schemes without printing the sensitive values themselves.

## Finding 3 - Tracked credential and duplicated database configuration

- Risk and evidence: the supplied current configuration stored a synthetic PostgreSQL credential in tracked `config/app.env` and separately in `docker-compose.yml`; the two values had already drifted apart.
- Impact: tracked credentials remain accessible to repository readers, and duplicated values can cause outages when only one copy changes.
- Implemented fix / commit: remove `config/app.env` from the current tree, source one local ignored `.env`, and publish a safe `.env.example`; `fix: restore database and cache connectivity`.
- Production follow-up: use a managed secret store with rotation and audit controls. The supplied lab value remains in the required immutable starter history, so it must never be reused for a real system.
- How to verify: `git check-ignore -v .env` identifies the ignore rule, the current tracked tree contains no active password, Compose validates quietly, and real dependency-backed endpoints succeed without exposing the value in saved evidence.

## Finding 4 - Unused Gunicorn control interface caused a startup error

- Risk and evidence: Gunicorn attempted to create its default control socket below `/home/app`, but the unprivileged user intentionally has no home directory. Both services logged a permission error even though request handling continued.
- Impact: noisy startup errors can hide real failures, and creating a writable home solely to satisfy an unused management interface would unnecessarily expand the container's writable surface.
- Implemented fix / commit: disable the unused control socket explicitly with `--no-control-socket`; `fix: disable unused gunicorn control socket`.
- Production follow-up: if runtime control becomes an operational requirement, provide a deliberate runtime directory, restrictive socket permissions, and documented access controls.
- How to verify: rebuild both apps, confirm their startup logs contain no `Control server error`, confirm both become healthy, and retest public `/health` and `/ready`.

## Finding 5 - PostgreSQL and Redis declared host publications

- Risk and evidence: the supplied Compose file declared loopback host mappings for PostgreSQL and Redis even though only NGINX is intended to be published.
- Impact: unnecessary host access increases the attack surface and enables clients on the workstation to bypass the application controls.
- Implemented fix / commit: remove both dependency `ports` declarations so only NGINX is published; `fix: enforce service network isolation`.
- Production follow-up: restrict database and cache ingress at the platform or firewall layer and use authenticated, audited administrative access when direct maintenance is required.
- How to verify: `docker port` returns a host mapping only for NGINX, while app, PostgreSQL, and Redis return no mappings.

## Finding 6 - NGINX had direct backend network access

- Risk and evidence: NGINX was attached to the backend network in addition to frontend, allowing the public-facing proxy a direct path to PostgreSQL and Redis.
- Impact: compromise or misconfiguration of the edge proxy could expose data services that it has no operational reason to contact.
- Implemented fix / commit: make NGINX frontend-only while keeping apps on both networks and data services backend-only; `fix: enforce service network isolation`.
- Production follow-up: apply default-deny network policies with explicit service-to-service rules and alert on unexpected east-west connections.
- How to verify: inspect each container's networks, confirm NGINX cannot resolve or connect to `postgres:5432` and `redis:6379`, then confirm both apps still report both dependencies ready.

## Finding 7 - Database and cache state was ephemeral

- Risk and evidence: PostgreSQL used tmpfs for its active data directory while its named volume targeted an unused path; Redis disabled persistence and had no data volume.
- Impact: container recreation or host maintenance could silently erase application records and counter state.
- Implemented fix / commit: mount PostgreSQL's active data path on `postgres-data`, remove its tmpfs, enable Redis AOF with `everysec`, and mount `redis-data` at `/data`; `fix: persist database and cache data`.
- Production follow-up: use storage appropriate to recovery objectives, monitor disk health and capacity, and maintain tested off-host backups. Named volumes alone are not backups.
- How to verify: create unique database/cache state, recreate all relevant containers without removing volumes, and require explicit PASS results for the surviving record and continuing counter.


For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.
