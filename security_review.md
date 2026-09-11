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
- Production follow-up: move credentials out of tracked configuration into the deployment platform's secret mechanism, rotate any value that has been exposed, and restrict access to images and logs. This finding is only partially complete until tracked credentials are removed.
- How to verify: assert that `/srv/app.env` is absent in a running app container and scan fresh app logs for PostgreSQL and Redis URL schemes without printing the sensitive values themselves.

For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.
