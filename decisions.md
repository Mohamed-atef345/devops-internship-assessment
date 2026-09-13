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

## Decision 5 - Separate edge and dependency traffic with two networks

- Choice: attach NGINX only to `frontend`, both app instances to `frontend` and the internal `backend`, and PostgreSQL/Redis only to `backend`; publish only NGINX on host loopback port 8080.
- Why: each service receives only the connectivity needed for its role, and all dependency traffic must pass through an application instance rather than the edge proxy or host.
- Alternative: keep every service on one shared network or attach NGINX to both networks, which is simpler but permits unnecessary direct paths to the data services.
- Trade-off: the application tier must bridge the two networks, and direct host database/cache access is unavailable for debugging unless a deliberate temporary method is used.
- Evidence / commit: network inspection matches the required topology, only NGINX has a host binding, NGINX cannot resolve the dependencies, and both apps remain ready; `fix: enforce service network isolation`.
- Production improvement: enforce equivalent network policies and ingress restrictions in the deployment platform and monitor denied connection attempts.

## Decision 6 - Use named volumes with PostgreSQL-native and Redis AOF storage paths

- Choice: mount `postgres-data` at `/var/lib/postgresql/data`; enable Redis AOF with an `everysec` fsync policy and mount `redis-data` at `/data`.
- Why: each service writes directly to durable named storage at the path expected by its official image, allowing data to survive disposable container replacement.
- Alternative: retain PostgreSQL tmpfs and disabled Redis persistence, which is faster for temporary tests but intentionally loses state on recreation.
- Trade-off: persistent writes use disk and Redis `everysec` can lose approximately the most recent second during a sudden host failure; named volumes also require explicit lifecycle and backup management.
- Evidence / commit: a uniquely titled PostgreSQL record and Redis counter both survived forced recreation of the data and application containers; `fix: persist database and cache data`.
- Production improvement: select storage performance and durability classes from measured requirements, monitor capacity and latency, and use tested backup, restore, and retention policies.

## Decision 7 - Apply uniform restart policy with service-specific limits

- Choice: use `unless-stopped` for every long-running service, with CPU/memory limits sized by role rather than one identical limit.
- Why: unexpected process exits can recover automatically, deliberate failure-test stops remain stopped, and one service cannot consume all workstation resources.
- Alternative: use `always`, which can conflict with deliberate operator stops, or retain no restart/limits, which provides fewer availability and resource safeguards.
- Trade-off: restart policy does not remediate a running but unhealthy container, and limits selected for this small assessment require measurement before production use.
- Evidence / commit: Docker inspection showed `unless-stopped` plus non-zero memory and NanoCPU limits on all five containers; `fix: harden service availability and failover`.
- Production improvement: tune requests/limits from observed utilization and use an orchestrator with separate liveness, readiness, restart-backoff, and disruption controls.

## Decision 8 - Bound NGINX retry and temporary backend failure handling

- Choice: retry only connection/proxy failures across at most two upstream attempts within four seconds, with per-operation timeouts and five-second failure windows.
- Why: one stopped backend should not interrupt service or leave clients waiting indefinitely, while a recovered backend should rejoin quickly.
- Alternative: disable retries, which exposed single-backend failures, or retry broadly without limits, which can amplify latency and duplicate unsafe operations.
- Trade-off: `max_fails=3` tolerates transient errors but can cause several retries before a backend is temporarily avoided; shared dependency failures are not solved by another app instance.
- Evidence / commit: all requests during the `app-01` stop were served by `app-02`, NGINX remained healthy, and both identities appeared after recovery; `fix: harden service availability and failover`.
- Production improvement: use measured latency/error budgets, passive and active health telemetry, and load testing to tune thresholds.

## Decision 9 - Keep full-stack validation bounded and configuration-aware

- Choice: implement one Python validator that discovers configured `app-*` services and the running NGINX port, performs bounded public API checks, proves real PostgreSQL/Redis operations, and inspects host ports and network membership.
- Why: one reusable command provides the required PASS/FAIL evidence before and after the live change from two apps/port 8080 to three apps/port 8090 without duplicating validation logic.
- Alternative: hard-code two backends and port 8080 or discover only running services, which is shorter but can fail after the final change or falsely pass when a configured backend is stopped.
- Trade-off: validation requires Docker API access and intentionally adds one uniquely named PostgreSQL record plus two Redis counter increments on each successful run.
- Evidence / commit: the healthy run passed every check and observed both app identities; an unused-port run failed within two seconds with exit 1; `test: add bounded full-stack validation`.
- Production improvement: publish machine-readable test output and run the same checks from an external monitoring location with authenticated access rather than relying only on the local Docker socket.

## Decision 10 - Use a scoped Bash failure test with guaranteed cleanup

- Choice: use one executable Bash script to stop `app-01`, measure 20 public `/instance` requests, restore the backend through an EXIT trap, and poll until the recovered identity serves traffic.
- Why: the workflow is primarily Compose and HTTP orchestration, so Bash keeps the implementation direct while the cleanup trap protects the lab during failed assertions.
- Alternative: retain the supplied Python placeholder or duplicate full-stack validation in the failure test; neither provides the required focused outage/recovery proof.
- Trade-off: the script relies on local `curl`, `jq`, Docker access, and the required `app-01` name; every run briefly removes one backend and produces public access-log traffic.
- Evidence / commit: the final run measured 20 successes, zero failures, `app-02` during the outage, and `app-01` after recovery; `test: add backend failure and recovery proof`.
- Production improvement: run equivalent controlled failure experiments in a safe staging environment with service-level metrics, alert assertions, and broader failure modes.

## Decision 11 - Pair an atomic SQL backup with transactional restore

- Choice: create a plain SQL dump through `pg_dump --clean --if-exists` into a temporary file, publish it only when non-empty, and restore it through `psql` with stop-on-error inside one transaction.
- Why: the two short scripts use tools already present in the PostgreSQL image and make both incomplete backup creation and partial SQL restoration fail clearly.
- Alternative: use a custom-format dump with `pg_restore`, which offers selective and parallel restore features but adds options not needed for this small single-schema assessment.
- Trade-off: the ignored plain SQL file is readable and unencrypted, and restoring intentionally replaces current database objects and data with the snapshot.
- Evidence / commit: a 2.1 KiB ignored dump restored nine records; the pre-backup record remained, the post-backup record disappeared, readiness stayed healthy, and full validation passed; `feat: add postgres backup and restore workflow`.
- Production improvement: encrypt backups, restrict permissions, store them off-host, define retention, schedule backups, monitor jobs, and regularly test recovery objectives against isolated restore targets.

## Decision 12 - Keep CI in one job and scan one application image

- Choice: use one GitHub Actions job for configuration checks, build, startup, validation, Trivy scanning, and cleanup; inject the CI-only database password through a repository secret.
- Why: GitHub Actions jobs have separate workspaces, so one job keeps the generated `.env` and built images available without artifact transfer or repeated setup. All application instances share the same image contents, so scanning one avoids duplicate results.
- Alternative: use separate jobs with repeated checkout and `.env` creation, or publish and transfer an image between jobs; both add complexity without improving this assessment.
- Trade-off: the stages do not run in parallel, and the workflow cannot run successfully until `POSTGRES_PASSWORD` is configured. A HIGH or CRITICAL fixable vulnerability also blocks CI.
- Evidence / commit: `.github/workflows/ci.yml`; `ci: add full-stack workflow and image scan`. Successful GitHub Actions run pending.
- Production improvement: pin third-party Actions to reviewed commit SHAs, retain scan reports, define a reviewed exception process, and add deployment only when a real protected target exists.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.
