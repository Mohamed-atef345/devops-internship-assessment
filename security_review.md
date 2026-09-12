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

For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.
