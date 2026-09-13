# Troubleshooting journal

## Entry 1 - 2026-09-11 15:07-15:31 EEST (12:07-12:31 UTC)

### Scope and starting state

- Starting commit: `8442da3` on `main`, with a clean tracked working tree.
- Compose project: `barq-assessment`.
- Purpose: establish the supplied baseline before changing any technical file.
- No remediation was attempted during this entry.

### 1. App only baseline

- Symptom: the first local test attempt could not import `psycopg` because the project dependencies were not installed in the local environment.
- Hypothesis: this was a workstation setup issue rather than a defect in the Flask application.
- Commands or tests:

  ```bash
  source .venv/bin/activate
  python -m pip install -r requirements.txt
  python -m pip check
  python -m unittest discover -s tests -v
  ```

- Actual result: dependency installation completed, `pip check` reported no broken requirements, and all 8 supplied unit tests passed.

  ```text
  No broken requirements found.

  Ran 8 tests in 0.029s
  OK
  ```

- Failed attempt and what changed my thinking: running the tests before installing dependencies failed at import time. Installing the pinned requirements allowed the tests to run and separated local setup from application behavior.
- Conclusion: the Flask contract passes with the tests' fake dependency implementation. This does not prove Docker networking, NGINX, PostgreSQL, Redis, or persistence.
- Fix: none required in the application for this result.
- Retest evidence: `Ran 8 tests ... OK`.

### 2. Initial Compose startup

- Symptom: the images built and all five containers started, but both app containers became unhealthy and none of the six public endpoint requests succeeded.
- Hypothesis: the stack contained more than one independent configuration failure, so the request path needed to be tested one boundary at a time.
- Commands or tests:

  ```bash
  docker compose -p barq-assessment config --quiet
  docker compose -p barq-assessment up --build -d
  docker compose -p barq-assessment ps -a
  docker compose -p barq-assessment logs --no-color --tail=200
  docker inspect \
    --format '{{.Name}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
    app-01 app-02 nginx postgres redis
  curl -i --max-time 5 http://127.0.0.1:8080/health
  ```

- Actual result:
  - `postgres` and `redis` were running and healthy.
  - `app-01` and `app-02` were running but unhealthy.
  - `nginx` was running without a health check.
  - The public request to `127.0.0.1:8080` was reset instead of returning an HTTP response.

  ```text
  /app-01   status=running health=unhealthy
  /app-02   status=running health=unhealthy
  /nginx    status=running health=none
  /postgres status=running health=healthy
  /redis    status=running health=healthy
  ```

- Root cause status: not assigned from container state alone; the following boundary tests isolated the causes.

### 3. Public port and NGINX listener mismatch

- Symptom: public requests to host port 8080 were reset.
- Hypothesis: Docker was forwarding host traffic to a container port on which NGINX was not listening.
- Commands or tests:

  ```bash
  docker port nginx
  docker exec nginx nginx -T
  docker exec nginx wget -S -O - http://127.0.0.1:80/
  docker exec nginx wget -S -O - http://127.0.0.1:81/
  ```

- Actual result:
  - Docker published `127.0.0.1:8080` to NGINX container port `81`.
  - The effective NGINX configuration contained `listen 80;`.
  - Port 81 refused the internal connection.
  - Port 80 reached NGINX and returned `502 Bad Gateway`.

  ```text
  81/tcp -> 127.0.0.1:8080
  listen 80;
  http://127.0.0.1:80/ -> HTTP/1.1 502 Bad Gateway
  http://127.0.0.1:81/ -> Connection refused
  ```

- Failed attempt and what changed my thinking: requesting NGINX on port 81 failed, but retrying the actual listener on port 80 reached the proxy and revealed a second upstream problem. This showed that the public reset and upstream 502 were separate failure layers.
- Root cause: the Compose host mapping targets container port 81 while NGINX listens on container port 80.
- Fix: pending.
- Retest evidence: pending; repeat the public curl and both internal listener tests after the fix.

### 4. NGINX-to-application connectivity

- Symptom: NGINX returned 502 on its real listener and direct NGINX requests to both app services were refused.
- Hypotheses:
  - Flask was bound only to each container's loopback interface.
  - At least one configured NGINX upstream port was incorrect.
- Commands or tests:

  ```bash
  docker exec app-01 python -c 'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2); print(r.status, r.read().decode())'
  docker exec app-02 python -c 'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2); print(r.status, r.read().decode())'
  docker exec nginx wget -S -O - http://app-01:8080/health
  docker exec nginx wget -S -O - http://app-02:8080/health
  docker exec nginx nginx -T
  ```

- Actual result:
  - Both apps returned HTTP 200 when called through their own `127.0.0.1:8080`.
  - NGINX resolved both Compose service names, but connections to `app-01:8080` and `app-02:8080` were refused.
  - The apps announced `Running on http://127.0.0.1:8080` in their logs.
  - NGINX configured `app-01:8081` and `app-02:8080` as upstreams.

  ```text
  app-01 localhost /health -> 200
  app-02 localhost /health -> 200
  nginx -> app-01:8080     -> Connection refused
  nginx -> app-02:8080     -> Connection refused

  upstream application_pool {
      server app-01:8081 max_fails=0;
      server app-02:8080 max_fails=0;
  }
  ```

- Root causes:
  - The apps bind to `127.0.0.1`, making them unreachable through the container network.
  - The `app-01` NGINX upstream uses port 8081 instead of 8080.
- Fix: pending.
- Retest evidence: pending; NGINX must reach both service names on the correct internal port and public requests must return successfully.

### 5. Application health check and backend identity

- Symptoms:
  - Both app containers remained unhealthy even though `/health` returned 200 internally.
  - Both containers returned `instance_id` value `app-01`.
- Hypotheses:
  - The Compose health check used the wrong endpoint.
  - The `app-02` instance environment value duplicated `app-01`.
- Commands or tests:

  ```bash
  docker compose -p barq-assessment logs --no-color --tail=40 app-01
  docker exec app-01 python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).read().decode())'
  docker exec app-02 python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).read().decode())'
  ```

- Actual result:
  - The health check repeatedly requested `/healthz` and received 404.
  - The application contract and successful direct test use `/health`.
  - Both direct responses contained `instance_id: app-01`.

  ```text
  GET /healthz HTTP/1.1 -> 404
  app-01 /health -> 200, instance_id=app-01
  app-02 /health -> 200, instance_id=app-01
  ```

- Root causes:
  - The configured container health check calls nonexistent `/healthz` instead of `/health`.
  - `app-02` is configured with the duplicate identity `app-01`.
- Fix: pending.
- Retest evidence: pending; both containers must become healthy and repeated `/instance` calls must show both distinct identities.

### 6. PostgreSQL and Redis readiness

- Symptom: application liveness worked, but `/ready`, `/records`, and `/counter` failed with dependency errors.
- Hypothesis: the application connection values did not match the live service ports and credentials.
- Command or test:

  ```bash
  docker exec -i app-01 python - <<'PY'
  import urllib.error
  import urllib.request

  for path in ["/", "/health", "/ready", "/instance", "/records", "/counter"]:
      url = "http://127.0.0.1:8080" + path
      try:
          response = urllib.request.urlopen(url, timeout=5)
          print(path, response.status, response.read().decode())
      except urllib.error.HTTPError as error:
          print(path, error.code, error.read().decode())
      except Exception as error:
          print(path, type(error).__name__, str(error))
  PY
  ```

- Actual result:
  - `/`, `/health`, and `/instance` returned 200.
  - `/ready` returned 503 with both PostgreSQL and Redis unavailable.
  - `/records` returned 503 `postgres_unavailable`.
  - `/counter` returned 503 `redis_unavailable`.
  - PostgreSQL listened on its standard container port 5432 while the app targeted 5433.
  - Redis listened on its standard container port 6379 while the app targeted 6380.
  - The configured PostgreSQL password value also differed between the app URL and database service. The values are intentionally omitted here.

  ```text
  /         -> 200
  /health   -> 200 status=alive
  /ready    -> 503 postgres=unavailable redis=unavailable
  /instance -> 200
  /records  -> 503 postgres_unavailable
  /counter  -> 503 redis_unavailable
  ```

- Root causes:
  - PostgreSQL host/port/password settings are inconsistent with the Compose service.
  - Redis is addressed on the wrong internal port.
- Fix: pending.
- Retest evidence: pending; `/ready`, `/records`, and `/counter` must perform successful real dependency operations.

### 7. Network isolation and prohibited host exposure

- Symptoms:
  - NGINX had direct membership in the backend network.
  - Compose requested PostgreSQL and Redis host port mappings even though only NGINX may be published.
- Commands or tests:

  ```bash
  for container in app-01 app-02 nginx postgres redis; do
    docker inspect \
      --format '{{.Name}}: {{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' \
      "$container"
  done

  docker inspect --format '{{json .HostConfig.PortBindings}}' nginx postgres redis
  ```

- Actual result:
  - `app-01` and `app-02` belonged to frontend and backend.
  - `nginx` also belonged to frontend and backend.
  - PostgreSQL and Redis belonged to backend only.
  - Container `HostConfig.PortBindings` requested PostgreSQL on loopback port 15432 and Redis on loopback port 16379.
  - In this run, `docker port` printed no active PostgreSQL/Redis mapping and `NetworkSettings.Ports` reported null for both. Therefore, this entry does not claim that those two ports were reachable from the host.

  ```text
  app-01:  barq-assessment_backend barq-assessment_frontend
  app-02:  barq-assessment_backend barq-assessment_frontend
  nginx:   barq-assessment_backend barq-assessment_frontend
  postgres: barq-assessment_backend
  redis:    barq-assessment_backend

  postgres HostConfig: 5432/tcp -> 127.0.0.1:15432
  redis HostConfig:    6379/tcp -> 127.0.0.1:16379
  postgres/redis active NetworkSettings port bindings: null
  ```

- Root causes:
  - NGINX is incorrectly attached to backend.
  - PostgreSQL and Redis declare prohibited Compose host port mappings; they must be removed even though Docker did not activate them in this run.
- Fix: pending.
- Retest evidence: pending; NGINX must be frontend-only and Docker inspection must show no host bindings for the apps, PostgreSQL, or Redis.

### 8. Persistence, secrets, and runtime policy

- Symptoms and observations:
  - The named PostgreSQL volume did not contain the active database data directory.
  - Redis persistence was disabled.
  - A database credential crossed tracked configuration, image, runtime environment, and log boundaries.
  - The app ran as root with Flask's development server.
  - Restart policies, resource limits, and an NGINX health check were absent.
- Commands or tests:

  ```bash
  docker inspect \
    --format '{{.Name}}: {{range .Mounts}}{{.Type}} {{.Name}} -> {{.Destination}}; {{end}}' \
    postgres redis
  docker inspect --format '{{json .HostConfig.Tmpfs}}' postgres
  docker inspect --format '{{json .Config.Cmd}}' redis
  docker inspect --format '{{.Config.User}}' app-01
  docker inspect --format '{{.HostConfig.RestartPolicy.Name}} memory={{.HostConfig.Memory}} nano_cpus={{.HostConfig.NanoCpus}}' app-01 app-02 nginx postgres redis
  docker compose -p barq-assessment logs --no-color app-01
  ```

- Actual result:
  - `postgres-data` was mounted at `/var/lib/postgresql/backup`, while `/var/lib/postgresql/data` used tmpfs.
  - Redis started with snapshotting disabled and append-only persistence disabled.
  - The Dockerfile copied the tracked connection configuration into the image, and the app printed the complete connection URLs at startup.
  - The app container user was `root`; logs showed Flask's development-server warning even though Gunicorn is an installed dependency.
  - Inspected restart policy was `no`, and configured memory/CPU limits were zero.
  - NGINX had no container health check.

  ```text
  postgres-data -> /var/lib/postgresql/backup
  tmpfs         -> /var/lib/postgresql/data
  Redis command -> --save "" --appendonly no
  app user      -> root
  restart       -> no
  memory        -> 0
  nano_cpus     -> 0
  ```

- Root causes: incorrect storage targets and runtime/security defaults in the supplied Dockerfile and Compose configuration.
- Fix: pending. Secret values must not be repeated in documentation or commits beyond the immutable supplied baseline.
- Retest evidence: pending; prove persistence separately from backup/restore, inspect the final image/runtime, and verify resource/restart/health configuration.

### Summary and next action

- What failed first: the public request could not reach the NGINX listener because host port 8080 mapped to unused container port 81.
- What proved it: live port bindings, the effective NGINX configuration, and contrasting internal requests to ports 80 and 81.
- Useful failed attempt: calling port 81 from inside NGINX failed; calling port 80 reached NGINX and returned 502, revealing the next layer rather than disproving the original diagnosis.
- Implemented fixes: none in this entry; the broken baseline was intentionally preserved.
- Related commit: the commit introducing this entry, `docs: record initial environment investigation`.
- Remaining uncertainty:
  - The exact behavior after each repair must be measured rather than assumed.
  - Real record creation, counter increment, load balancing, failover, recovery, and persistence remain unproved.
  - Historical log analysis is a separate incident and has not started.
  - Required validation, failure, backup/restore, CI, architecture, security, decision, AI, and evidence deliverables remain incomplete.

---

## Entry 2 - 2026-09-11 16:31-16:50 EEST (13:31-13:50 UTC)

### Scope

- Purpose: restore the application runtime and the public NGINX request path while keeping the database and cache repair as a separate, reviewable change.
- Files changed: `Dockerfile`, `app/server.py`, `docker-compose.yml`, and `nginx/nginx.conf`.
- This entry verifies application liveness and proxy load balancing. It does not claim that PostgreSQL or Redis connectivity is fixed.

### Fixes applied

- Replaced the Flask development server with Gunicorn and used the application factory `app.server:create_app()`.
- Ran the application as the unprivileged `app` user and stopped copying `config/app.env` into the image.
- Bound the application to `0.0.0.0:8080` so it is reachable through the Compose network.
- Changed the app health check from nonexistent `/healthz` to the liveness endpoint `/health`.
- Corrected `app-02`'s `INSTANCE_ID` and the `app-01` NGINX upstream port.
- Corrected the NGINX publication from host `127.0.0.1:8080` to container port 80.
- Replaced connection-URL logging with safe booleans indicating only whether each variable is configured.

### Verification commands

```bash
git diff --check
docker compose -p barq-assessment config --quiet
source .venv/bin/activate
python -m unittest discover -s tests -v
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a

docker exec nginx wget -S -O - http://app-01:8080/health
docker exec nginx wget -S -O - http://app-02:8080/health

docker exec app-01 sh -c \
  'if [ -e /srv/app.env ]; then echo "FAIL: app.env exists"; exit 1; else echo "PASS: app.env absent"; fi'

if docker compose -p barq-assessment logs --no-color app-01 app-02 | \
  grep -Eq 'postgresql://|redis://'; then
  echo "FAIL: connection URL found in logs"
else
  echo "PASS: no connection URLs in logs"
fi

for i in {1..20}; do
  curl -sS --max-time 3 http://127.0.0.1:8080/instance |
    python -c 'import json, sys; print(json.load(sys.stdin)["instance_id"])'
done | sort | uniq -c
```

### Actual results

- All 8 supplied unit tests passed.
- `app-01`, `app-02`, PostgreSQL, and Redis reported healthy; NGINX was running and exposed only as `127.0.0.1:8080->80/tcp`.
- NGINX reached both application services on port 8080. Each returned HTTP 200 from Gunicorn with the correct instance identity.
- Public `/`, `/health`, and `/instance` requests returned HTTP 200 through NGINX.
- Twenty public `/instance` requests reached both backends:

  ```text
  15 app-01
   5 app-02
  ```

- `/srv/app.env` was absent from the application image.
- The application logs contained no PostgreSQL or Redis connection URLs.

### Diagnosis-to-evidence mapping

| Baseline fault | Applied correction | Retest evidence |
| --- | --- | --- |
| App bound only to container loopback | Bind Gunicorn to `0.0.0.0:8080` | NGINX reached both apps and received HTTP 200 |
| NGINX published to unused port 81 | Publish host 8080 to NGINX port 80 | Public endpoints returned HTTP 200 |
| `app-01` upstream used port 8081 | Use port 8080 for both upstreams | Both direct upstream health requests succeeded |
| Health check requested `/healthz` | Check `/health` | Both app containers became healthy |
| Both services identified as `app-01` | Set the second ID to `app-02` | Load-balancing sample contained both identities |
| Development server ran as root | Use Gunicorn as user `app` | Container process inspection showed UID 10001 and Gunicorn workers |
| Configuration file was copied into the image and URLs were logged | Remove the copy and log only configured/not-configured booleans | `/srv/app.env` was absent and the connection-URL log scan passed |

### Failed or limited verification attempt

- Three initial public requests all happened to reach `app-01`. That sample proved the proxy path but was too small to demonstrate load balancing. Increasing the sample to 20 requests showed both `app-01` and `app-02`. The uneven 15/5 result is sufficient to prove that both backends receive traffic; with multiple NGINX workers and a short sample, it should not be treated as a precise traffic-distribution measurement.

### Remaining work

- `/ready`, `/records`, and `/counter` still return HTTP 503 because the PostgreSQL and Redis connection settings remain intentionally unfixed for the next focused change.
- Persistence, network isolation, prohibited dependency port declarations, restart policies, resource limits, NGINX health/failover behavior, backup/restore, CI, and failure demonstrations remain pending.
- Related commit: the commit containing this entry, `fix: restore app and nginx connectivity`.

---

## Entry 3 - 2026-09-12 18:02-18:16 EEST (15:02-15:16 UTC)

### Scope

- Purpose: restore real PostgreSQL and Redis connectivity through both application instances and remove the tracked runtime connection file from the current project state.
- Files changed: `.env.example`, `config/app.env`, and `docker-compose.yml`.
- Persistence, host-port removal, and network isolation are intentionally outside this change and remain separate milestones.

### Symptoms and hypothesis

- `/ready` previously returned HTTP 503 with both dependencies unavailable; `/records` and `/counter` returned dependency-specific 503 responses.
- The application connection configuration targeted nonstandard internal ports, and the PostgreSQL password did not match the database service configuration.
- Hypothesis: using Compose service names with their real container ports and one shared local PostgreSQL configuration would restore both dependencies.

### Fixes applied

- Removed the tracked `config/app.env` file and stopped using it as an application `env_file`.
- Added safe variable names and a placeholder password to `.env.example`; the real synthetic lab value remains only in the ignored local `.env` file.
- Constructed `DATABASE_URL` from the local PostgreSQL variables and used the service address `postgres:5432`.
- Set `REDIS_URL` to the service address `redis:6379/0`.
- Configured the PostgreSQL service and application URL from the same user, database, and password variables, eliminating the mismatch.

### Verification commands

```bash
git check-ignore -v .env
docker compose -p barq-assessment config --quiet
git diff --check
source .venv/bin/activate
python -m unittest discover -s tests -v
docker compose -p barq-assessment up --build -d --force-recreate \
  postgres redis app-01 app-02 nginx
docker compose -p barq-assessment ps -a

docker exec app-01 python -c \
  'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/ready", timeout=5); print(r.status, r.read().decode())'
docker exec app-02 python -c \
  'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/ready", timeout=5); print(r.status, r.read().decode())'

curl -i --max-time 5 http://127.0.0.1:8080/ready
curl -i --max-time 5 \
  -H 'Content-Type: application/json' \
  -d '{"title":"PostgreSQL connectivity proof"}' \
  http://127.0.0.1:8080/records
curl -i --max-time 5 http://127.0.0.1:8080/records
curl -i --max-time 5 http://127.0.0.1:8080/counter
curl -i --max-time 5 http://127.0.0.1:8080/counter
```

### Actual results

- `.env` was confirmed ignored by the repository's `.gitignore`.
- Compose validation and `git diff --check` completed without errors, and all 8 supplied unit tests passed.
- Both application instances returned HTTP 200 from their own `/ready` endpoints with PostgreSQL and Redis reported as `ready`.
- The public `/ready` endpoint returned HTTP 200 through NGINX.
- POST `/records` returned HTTP 201 and created record ID 3 with the synthetic title `PostgreSQL connectivity proof`; the following GET `/records` returned that record with the two initialized records.
- Two public `/counter` calls returned HTTP 200 and values 1 then 2, proving a real shared Redis increment.
- `docker compose ps -a` showed both apps, PostgreSQL, and Redis healthy. Only NGINX had an active host publication in that runtime output.

### Failed attempts and new observation

- Fresh application logs revealed `Control server error: Permission denied: '/home/app'` from Gunicorn. Requests and health checks still succeeded, so this did not invalidate the database/cache connectivity evidence. It is a separate unresolved runtime warning: Gunicorn 26.2 attempts to create its default control socket below the configured user's home, while the image creates that user with `--no-create-home`.

### Root cause and conclusion

- Root cause: the app used incorrect internal ports for both dependencies, PostgreSQL credentials were inconsistent between the app and database, and the connection file was tracked instead of being supplied locally.
- Conclusion: real PostgreSQL and Redis operations now succeed through both app configuration and the public NGINX path. This entry does not prove data persistence across container recreation.
- Related commit: the commit containing this entry, `fix: restore database and cache connectivity`.

### Remaining work

- Resolve and retest the Gunicorn control-socket permission warning before treating application startup logs as clean.
- Correct PostgreSQL and Redis persistence and prove survival across container recreation.
- Remove prohibited PostgreSQL and Redis host-port declarations and enforce the required frontend/backend network isolation.
- Restart policies, resource limits, NGINX health/failover behavior, validation and failure scripts, backup/restore, CI, architecture, log analysis, and final evidence remain pending.

---

## Entry 4 - 2026-09-12 18:29-18:38 EEST (15:29-15:38 UTC)

### Scope

- Purpose: remove the Gunicorn control-socket startup error without changing application behavior.
- File changed: `Dockerfile`.
- This is a focused follow-up to the warning discovered during the database/cache connectivity verification.

### Symptom and hypothesis

- Symptom: both app containers served requests successfully, but each fresh Gunicorn startup logged `Control server error: Permission denied: '/home/app'`.
- Root-cause hypothesis: Gunicorn 26.2 enables its control socket by default and falls back to a path below the configured user's home. The image deliberately creates the unprivileged `app` user with `--no-create-home`, so that location is unavailable.

### Fix

- Added `--no-control-socket` to the Gunicorn command.
- The control interface is not used by this assessment, so disabling it removes the unnecessary writable-path requirement while retaining the non-root user and two-worker runtime.

### Verification commands

```bash
docker compose -p barq-assessment up --build -d --force-recreate \
  app-01 app-02 nginx
docker compose -p barq-assessment ps -a
docker compose -p barq-assessment logs \
  --no-color --since=3m app-01 app-02

if docker compose -p barq-assessment logs --no-color --since=3m app-01 app-02 |
  grep -Fq "Control server error"; then
  echo "FAIL: Gunicorn control socket error remains"
else
  echo "PASS: no Gunicorn control socket error"
fi

curl -i --max-time 5 http://127.0.0.1:8080/health
curl -i --max-time 5 http://127.0.0.1:8080/ready
```

### Actual results

- Both application images rebuilt and both app containers restarted successfully.
- The first immediate `ps` check showed `health: starting`; after the health-check interval, both app containers reported `healthy`.
- Fresh startup logs showed Gunicorn 26.2 listening on `0.0.0.0:8080` and booting two workers for each instance without the previous permission error.
- The explicit log scan returned `PASS: no Gunicorn control socket error`.
- Public `/health` returned HTTP 200 and `/ready` returned HTTP 200 with PostgreSQL and Redis both `ready`.

### Conclusion

- Root cause confirmed: an enabled but unused Gunicorn control socket required a writable home path that the intentionally no-home application user did not have.
- Retest evidence confirms that disabling only this unused interface removes the error while preserving liveness and dependency readiness.
- Related commit: the commit containing this entry, `fix: disable unused gunicorn control socket`.

### Remaining work

- PostgreSQL and Redis persistence, network isolation and prohibited dependency ports remain the next infrastructure milestones.
- Restart policies, resource limits, NGINX health/failover behavior, validation and failure scripts, backup/restore, CI, architecture, log analysis, and final evidence remain pending.

---

## Entry 5 - 2026-09-12 18:44-18:49 EEST (15:44-15:49 UTC)

### Scope

- Purpose: enforce the required frontend/backend network boundary and remove prohibited host publications from PostgreSQL and Redis.
- File changed: `docker-compose.yml`.
- Persistence and service availability hardening remain separate milestones.

### Symptoms and hypothesis

- NGINX previously belonged to both `frontend` and `backend`, which gave the edge proxy unnecessary direct network access to PostgreSQL and Redis.
- PostgreSQL and Redis declared loopback host-port mappings even though the assessment permits publishing only NGINX.
- Hypothesis: making NGINX frontend-only and removing the two dependency port declarations would block both access paths without breaking app-to-dependency communication.

### Fixes applied

- Removed NGINX from the `backend` network while retaining its `frontend` membership.
- Kept both app instances on `frontend` and `backend` so NGINX can reach them and they can reach the dependencies.
- Kept PostgreSQL and Redis on the internal `backend` network only.
- Removed the PostgreSQL and Redis host-port declarations. Their standard container ports remain available only to services sharing the backend network.

### Verification commands

```bash
git diff --check
docker compose -p barq-assessment config --quiet
docker compose -p barq-assessment up -d --force-recreate \
  postgres redis nginx
docker compose -p barq-assessment ps -a

for container in nginx app-01 app-02 postgres redis; do
  docker inspect \
    --format '{{.Name}}: {{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' \
    "$container"
done

docker port nginx
docker port app-01
docker port app-02
docker port postgres
docker port redis

docker exec nginx sh -c 'nc -z -w 2 postgres 5432'
docker exec nginx sh -c 'nc -z -w 2 redis 6379'

docker exec app-01 python -c \
  'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/ready", timeout=5); print(r.status, r.read().decode())'
docker exec app-02 python -c \
  'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8080/ready", timeout=5); print(r.status, r.read().decode())'

curl -i --max-time 5 http://127.0.0.1:8080/health
curl -i --max-time 5 http://127.0.0.1:8080/ready
```

### Actual results

- Compose validation and `git diff --check` completed without errors.
- Network inspection showed:

  ```text
  nginx:    frontend
  app-01:   frontend, backend
  app-02:   frontend, backend
  postgres: backend
  redis:    backend
  ```

- `docker port nginx` reported `80/tcp -> 127.0.0.1:8080`; the app, PostgreSQL, and Redis port commands produced no host binding.
- Direct connection attempts from NGINX returned `bad address` for both dependency service names. This expected failure proves those names and ports are unavailable outside their shared backend network.
- Both app instances still returned HTTP 200 from `/ready` with PostgreSQL and Redis reported as `ready`.
- Public `/health` and `/ready` both returned HTTP 200 through NGINX after the isolation change.

### Conclusion

- Root cause: excess NGINX network membership and explicit dependency host-port declarations bypassed the intended least-privilege topology.
- Retest evidence confirms that clients can reach only NGINX, NGINX can reach the apps through `frontend`, and only the apps can reach PostgreSQL and Redis through `backend`.
- Related commit: the commit containing this entry, `fix: enforce service network isolation`.

### Remaining work

- Correct and prove PostgreSQL and Redis persistence across container recreation.
- Add restart policies, resource limits, NGINX health and bounded failover behavior.
- Validation and failure scripts, backup/restore, CI, architecture, log analysis, final README, and evidence index remain pending.

---

## Entry 6 - 2026-09-12 18:54-19:12 EEST (15:54-16:12 UTC)

### Scope

- Purpose: configure durable PostgreSQL and Redis storage and prove that real application data survives container recreation.
- File changed: `docker-compose.yml`.
- This test recreates containers while deliberately retaining named volumes; it is not the separate backup/restore deliverable.

### Symptoms and hypothesis

- PostgreSQL previously stored its active data directory in `tmpfs`, while the named volume was mounted at an unused backup path.
- Redis explicitly disabled both snapshotting and append-only persistence and had no data volume.
- Hypothesis: mounting the PostgreSQL named volume at its real data directory and enabling Redis AOF on a named `/data` volume would preserve both data stores across container replacement.

### Fixes applied

- Mounted `postgres-data` at `/var/lib/postgresql/data` and removed the PostgreSQL data-directory `tmpfs`.
- Enabled Redis append-only persistence with `appendonly yes` and `appendfsync everysec`.
- Mounted a new named `redis-data` volume at `/data` and declared it in the top-level volume list.

### Commands used for the persistence proof

```bash
docker compose -p barq-assessment up -d --force-recreate \
  postgres redis app-01 app-02 nginx
docker compose -p barq-assessment ps -a
curl -i --max-time 5 http://127.0.0.1:8080/ready

docker exec redis redis-cli CONFIG GET appendonly
docker exec redis redis-cli CONFIG GET appendfsync

PERSISTENCE_PROOF_TITLE="Persistence proof $(date -u +%Y%m%dT%H%M%SZ)"
echo "$PERSISTENCE_PROOF_TITLE"
curl -i --max-time 5 \
  -H 'Content-Type: application/json' \
  --data "$(printf '{"title":"%s"}' "$PERSISTENCE_PROOF_TITLE")" \
  http://127.0.0.1:8080/records

REDIS_COUNTER_BEFORE=$(
  curl -fsS --max-time 5 http://127.0.0.1:8080/counter |
    python -c 'import json,sys; print(json.load(sys.stdin)["counter"])'
)
echo "Redis counter before recreation: $REDIS_COUNTER_BEFORE"
sleep 2

docker compose -p barq-assessment up -d --force-recreate \
  postgres redis app-01 app-02 nginx
docker compose -p barq-assessment ps -a
curl -i --max-time 5 http://127.0.0.1:8080/ready

curl -fsS --max-time 5 http://127.0.0.1:8080/records |
  python -c '
import json
import sys
expected = sys.argv[1]
titles = [record["title"] for record in json.load(sys.stdin)["records"]]
if expected not in titles:
    raise SystemExit("FAIL: PostgreSQL record did not survive")
print("PASS: PostgreSQL record survived:", expected)
' "$PERSISTENCE_PROOF_TITLE"

REDIS_COUNTER_AFTER=$(
  curl -fsS --max-time 5 http://127.0.0.1:8080/counter |
    python -c 'import json,sys; print(json.load(sys.stdin)["counter"])'
)
echo "Redis counter after recreation: $REDIS_COUNTER_AFTER"
if [ "$REDIS_COUNTER_AFTER" -eq "$((REDIS_COUNTER_BEFORE + 1))" ]; then
  echo "PASS: Redis counter survived and continued"
else
  echo "FAIL: Redis counter did not continue"
fi
```

### Actual results

- After applying the storage configuration, PostgreSQL progressed from `health: starting` to `healthy`; both apps and Redis were also healthy, and public `/ready` returned HTTP 200.
- Runtime inspection confirmed `postgres-data` at `/var/lib/postgresql/data`, `redis-data` at `/data`, and no PostgreSQL data-directory tmpfs. The unfiltered inspection output is intentionally not reproduced because it also contained runtime environment values.
- Redis reported `appendonly yes` and `appendfsync everysec`.
- The successful POST created record ID 3 with title `Persistence proof 20260912T160449Z`.
- Before recreation, the Redis counter value was 1. A two-second delay allowed the `everysec` AOF policy to flush.
- All five service containers were force-recreated without removing either named volume. They returned healthy and public `/ready` returned HTTP 200 afterward.
- The PostgreSQL check printed `PASS: PostgreSQL record survived: Persistence proof 20260912T160449Z`.
- The first Redis request after recreation returned 2, exactly one greater than the saved value, and printed `PASS: Redis counter survived and continued`.

### Root cause and conclusion

- Root cause: the PostgreSQL volume did not cover the active database directory, tmpfs discarded that directory on container replacement, and Redis persistence was explicitly disabled with no persistent mount.
- Retest evidence proves both a PostgreSQL record and the Redis counter survived real container recreation using their named volumes.
- Related commit: the commit containing this entry, `fix: persist database and cache data`.

### Remaining work

- Implement and prove the separate PostgreSQL backup and restore workflow.
- Add restart policies, resource limits, NGINX health and bounded failover behavior.
- Validation and failure scripts, CI, architecture, historical log analysis, final README, and evidence index remain pending.

---

## Entry 7 - 2026-09-12 19:24-19:40 EEST (16:24-16:40 UTC)

### Scope

- Purpose: add restart policies, CPU/memory limits, an NGINX health check, and bounded upstream failure handling; then prove continued service with one app stopped and recovery after it returns.
- Files changed: `docker-compose.yml` and `nginx/nginx.conf`.
- This is a manual availability verification. The required reusable `failure_test.py` and its traffic/error measurements remain a separate deliverable.

### Baseline risks and hypothesis

- All services previously used restart policy `no`, resource limits were unset, and NGINX had no container health check.
- NGINX disabled upstream failure tracking with `max_fails=0` and disabled retry with `proxy_next_upstream off`.
- Hypothesis: bounded retry across two upstreams, temporary failure tracking, and an end-to-end NGINX health check would preserve public availability when one app is deliberately stopped.

### Fixes applied

- Set `restart: unless-stopped` on the shared app definition, NGINX, PostgreSQL, and Redis.
- Limited each app to 0.50 CPU and 256 MiB, NGINX to 0.25 CPU and 128 MiB, PostgreSQL to 0.75 CPU and 512 MiB, and Redis to 0.25 CPU and 256 MiB.
- Added an NGINX health check that requests `/health` through its local listener every five seconds.
- Configured both app upstreams with `max_fails=3` and `fail_timeout=5s`.
- Bounded upstream connection, send, and read waits to 1, 3, and 3 seconds respectively.
- Enabled retry for connection errors, timeouts, HTTP 502, and HTTP 504; capped processing at two upstream attempts and four seconds total. Non-idempotent retry was not enabled.

### Verification commands

```bash
docker compose -p barq-assessment up -d --force-recreate \
  postgres redis app-01 app-02 nginx
docker exec nginx nginx -t
docker compose -p barq-assessment ps -a

docker inspect \
  --format '{{.Name}} restart={{.HostConfig.RestartPolicy.Name}} memory={{.HostConfig.Memory}} nano_cpus={{.HostConfig.NanoCpus}}' \
  app-01 app-02 nginx postgres redis

curl -i --max-time 5 http://127.0.0.1:8080/health
curl -i --max-time 5 http://127.0.0.1:8080/ready

docker stop app-01
docker compose -p barq-assessment ps -a
curl -fsS --max-time 5 http://127.0.0.1:8080/instance

docker inspect \
  --format 'nginx health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
  nginx

docker start app-01
docker compose -p barq-assessment ps -a
curl -fsS --max-time 5 http://127.0.0.1:8080/instance
```

The `/instance` request was repeated while the backend was stopped and again after recovery.

### Actual results

- `nginx -t` reported valid syntax and a successful configuration test.
- The first immediate Compose status showed normal `health: starting` states. Subsequent status output showed every service healthy.
- Runtime inspection reported `unless-stopped` and the expected byte/NanoCPU limits for all five services:

  ```text
  app-01/app-02: memory=268435456 nano_cpus=500000000
  nginx:         memory=134217728 nano_cpus=250000000
  postgres:      memory=536870912 nano_cpus=750000000
  redis:         memory=268435456 nano_cpus=250000000
  ```

- Before failure injection, public `/health` and `/ready` returned HTTP 200.
- A deliberate `docker stop app-01` left that container exited, as expected for a manual stop under `unless-stopped`.
- Six consecutive public `/instance` requests succeeded through `app-02`; NGINX remained healthy throughout the single-backend outage.
- After `docker start app-01`, Compose showed it healthy. Repeated public requests then returned both `app-01` and `app-02`, proving recovery and reintegration.

### Root cause and conclusion

- Root cause: the supplied configuration had no lifecycle/resource guardrails and explicitly disabled NGINX failure tracking and retry.
- Retest evidence proves bounded single-backend failover and recovery while preserving public liveness, readiness, and NGINX health.
- Related commit: the commit containing this entry, `fix: harden service availability and failover`.

### Remaining work

- Implement `failure_test.py` to automate the outage, measure traffic and errors, restore the backend, and exit non-zero on failure.
- Implement full validation, PostgreSQL backup/restore, CI, architecture, historical log analysis, final README, and evidence index.
- The final video must still perform the one-time challenge, switch to port 8090, and add a third app instance.

---

## Entry 8 - 2026-09-12 approximately 20:03-21:08 EEST (17:03-18:08 UTC)

### Scope

- Purpose: replace the supplied `validate.py` placeholder with a minimal, bounded full-stack validator.
- File changed: `validate.py`.
- The validator checks the public API, real PostgreSQL and Redis operations, all configured application identities, prohibited host ports, and required network isolation.

### Initial implementation and review findings

- The candidate wrote the initial validator and ran it against the repaired stack.
- Review found that readiness was attempted only once, so normal dependency startup could cause a false failure instead of using the required bounded wait.
- Backend discovery used `docker compose ps --services`, which lists running services; a stopped app could disappear from the expected set and allow a false pass.
- The original default did not automatically follow the required later move from port 8080 to 8090 because Python does not automatically load Compose's `.env` values.
- The NGINX port check accepted any published binding rather than requiring the expected loopback-only binding.
- The first version duplicated several endpoint requests and mixed `curl` with Python HTTP handling.

### Fixes applied

- Added readiness polling with short request timeouts and a fixed overall `--timeout` deadline.
- Discover configured `app-*` services through `docker compose config --services`, including a configured backend that is currently stopped.
- Discover the running NGINX port automatically while retaining explicit `--url` and `--project` overrides.
- Require exactly one NGINX binding at `127.0.0.1:PUBLIC_PORT` and reject host bindings on the apps, PostgreSQL, or Redis.
- Require exact frontend/backend network membership for each service role.
- Consolidated HTTP status, JSON, request-ID, command-timeout, and failure handling into shared helpers and removed the `curl` dependency.
- Kept the validator intentionally scoped: it creates one uniquely named record and increments the counter, but it does not stop containers, test failover, restore backups, or run the recorded challenge.

### Verification commands

```bash
git diff --check
python3 validate.py
```

### Actual results

- The candidate's final healthy-stack run printed PASS for dependency readiness, both configured backends, `/`, `/health`, `/ready`, PostgreSQL record creation/retrieval, invalid-title handling, Redis, the unknown route, both observed identities, the loopback-only NGINX port, and network isolation.
- That run observed Redis increasing from 15 to 16 and ended with `ALL VALIDATION CHECKS PASSED`.
- The healthy run exited 0.
- The harmless unused-port test stopped after the two-second deadline, printed `FAIL: dependencies were not ready within 2 seconds`, and exited 1.
- Python compilation and `git diff --check` both succeeded.


### Conclusion

- The validator now provides bounded PASS/FAIL evidence for the minimum assessment requirements and returns a non-zero exit when a required condition is unavailable.
- It discovers the configured app set and current NGINX port, so the same script can be rerun after the recorded change to three apps on port 8090.
- Related commit: `test: add bounded full-stack validation` (the commit containing this entry and `validate.py`).

### Remaining work

- Commit the validator and this evidence as one cohesive validation milestone named `test: add bounded full-stack validation`.
- Implement `failure_test.py`, PostgreSQL backup/restore, CI, historical-log analysis, final README, architecture, and final evidence links.
- Rerun this validator during the final video after adding `app-03` and changing the public port to 8090.

---

## Entry 9 - 2026-09-13 14:32-15:57 EEST (11:32-12:57 UTC)

### Scope and timing

- Purpose: replace the Python failure-test placeholder with a minimal Bash test that measures availability during one backend outage and proves recovery.
- Files changed: removed `failure_test.py` and added executable `failure_test.sh`.
- Candidate-captured work began at `2026-09-13 14:32:12 EEST (+0300)` / `11:32:12 UTC` and ended at `15:52:36 EEST` / `12:52:36 UTC`.
- A final post-review run was captured from `15:57:26` to `15:57:36 EEST` / `12:57:26` to `12:57:36 UTC`.

### Failed attempts and lessons

- Unquoted `grep app-*` was expanded by Zsh and failed with `no matches found`; quoting the expression allowed the two app container names to be counted.
- Because those early versions lacked guaranteed cleanup, inspection at 15:16 showed `app-01` still exited while the remaining four services were running. This directly demonstrated why cleanup cannot depend only on reaching the normal restart lines.
- Later candidate runs at 15:23, 15:25, and 15:49 completed successfully. The 15:49 run reported `observed_app: app-02`, 20 successes, zero failures, and `app-01` serving again.

### Final implementation

- Discovers the published NGINX port from Compose so the test follows the later change from 8080 to 8090.
- Requires `app-01`, at least two running app containers, and public readiness before injecting failure.
- Stops only `app-01`, sends 20 bounded `/instance` requests, and counts successes and failures.
- Requires successful responses to contain a non-empty identity other than the stopped `app-01`.
- Registers an EXIT cleanup trap before stopping the backend, so an intermediate failure attempts to restore `app-01`.
- Restarts `app-01` and polls `/instance` until that identity is observed or the bounded attempts expire.
- Does not use `docker compose down`, change configuration, or touch volumes.

### Final verification

```bash
bash -n failure_test.sh
git diff --check
./failure_test.sh
```

The final run produced:

```text
PASS: app-01 is running
PASS: 2 app containers are running
PASS: /ready responded with 200
PASS: stopped app-01
Successes: 20
Failures: 0
observed_app: app-02
PASS: service remained available
PASS: restarted app-01
PASS: app-01 served traffic again
ALL FAILURE TESTS PASSED
```

- The final script exited 0.
- Shell syntax and `git diff --check` passed.
- The post-review run took ten seconds from 15:57:26 to 15:57:36 EEST.

### Conclusion

- The automated test proves that all 20 measured public requests remained available through `app-02` while `app-01` was stopped, and that the restored `app-01` subsequently served public traffic.
- Related commit: `test: add backend failure and recovery proof` (the commit containing `failure_test.sh` and this entry).

### Remaining work

- Implement and prove PostgreSQL backup and restore.
- Add CI, analyze the historical logs, replace the starter README, create the final architecture diagram, and complete submission evidence.

---

## Entry 10 - 2026-09-13 16:06-16:28 EEST (13:06-13:28 UTC)

### Scope and timing

- Purpose: implement and prove a real PostgreSQL logical backup and transactional restore.
- Files changed: `backup.sh` and `restore.sh`.
- The candidate captured the start at `2026-09-13 16:06:42 EEST (+0300)` / `13:06:42 UTC` and the end at `16:28:18 EEST` / `13:28:18 UTC`.

### Implementation

- `backup.sh` runs `pg_dump` inside the Compose-owned PostgreSQL container with clean, ownership-neutral SQL output.
- It writes to a temporary file, rejects an empty dump, then atomically moves the completed dump to the requested path.
- The default output directory is ignored `backups/`, preventing database contents from being committed accidentally.
- `restore.sh` requires one non-empty backup-file argument and passes it to `psql` inside the PostgreSQL container.
- Restore uses `ON_ERROR_STOP=1` and one transaction so a SQL error fails the script instead of reporting partial success.
- Both scripts use the existing container environment for the database name and user and do not print the password.

### Verification commands and evidence

- The candidate used commands supplied by OpenAI Codex to create a uniquely named record, back it up, create a second record after the snapshot, restore the snapshot, and revalidate the stack.
- `/ready` initially returned HTTP 200 with PostgreSQL and Redis both `ready`.
- The record retained in the backup was ID 9 with title `Backup proof 20260913T131147Z`.
- `./backup.sh` created `backups/restore-proof-20260913T131147Z.sql`.
- `ls -lh` reported a 2.1 KiB non-empty file, and `git check-ignore` printed its path, proving it is ignored.
- After the backup, the candidate created record ID 10 with title `Created after backup 20260913T131147Z`.
- A pre-restore query returned `true`, proving both unique records existed before restoration.
- `./restore.sh` completed the clean schema restore, copied nine records, reset the identity sequence to 9, and printed `PASS: backup restored`.
- Public readiness remained healthy after restoration.
- `python3 validate.py` passed every full-stack check, observed `app-01` and `app-02`, and incremented Redis from 17 to 18.
- A final read-only record check returned:

  ```json
  {
    "keep_present": true,
    "after_present": false
  }
  ```

  This proves the backed-up record survived and the record created after the snapshot was removed by restoration.
- `bash -n backup.sh restore.sh` and `git diff --check` passed.

### Conclusion

- Logical backup and restore are independently proven: the snapshot retained the pre-backup record and removed the post-backup record while the application returned to full readiness.
- This test did not remove Compose volumes and is separate from the earlier container-recreation persistence proof.
- Related commit: `feat: add postgres backup and restore workflow` (the commit containing both scripts and this evidence).

### Remaining work

- Add CI, analyze the historical logs, replace the starter README, create the final architecture diagram, and complete final submission evidence.

---

## Entry 11 - 2026-09-13 17:37-18:03 EEST (14:37-15:03 UTC)

### Scope and timing

- Purpose: add the required GitHub Actions CI workflow and the optional application-image vulnerability scan.
- File changed by the candidate: `.github/workflows/ci.yml`.
- Work began at approximately `2026-09-13 17:37 EEST (+0300)` / `14:37 UTC` and ended at `18:03:49 EEST (+0300)` / `15:03:49 UTC`.

### Implementation

- The workflow runs on pushes and pull requests targeting `main`.
- A repository Actions secret named `POSTGRES_PASSWORD` supplies the synthetic CI database password; the job creates a permission-restricted `.env` without printing the value.
- One job performs Python, Bash, and Compose configuration checks, builds the images, starts the complete stack with a bounded health wait, and runs `validate.py`.
- Trivy scans one application image for fixable HIGH and CRITICAL operating-system and library vulnerabilities. One image is sufficient because all app instances use the same Dockerfile and dependencies.
- Cleanup runs with `if: always()` and removes only the CI Compose project's containers, networks, and disposable volumes.
- No deployment job was added because this local assessment has no authorized deployment target.

### Initial verification

```bash
docker compose config -q
git diff --check
git status --short
```

- Local Compose configuration and whitespace checks passed.
- Commit `e751d08` triggered [CI run #1](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34764720196). Syntax, build, startup, and full-stack validation passed, but the Trivy security gate failed.
- The failure and successful remediation are recorded in Entry 12.

### Conclusion

- The workflow covers the required checkout, syntax/configuration, build, start, bounded wait, validation, failure propagation, and cleanup stages without duplicating failure or backup tests.
- The Trivy step supplies the optional image-scan evidence and intentionally fails CI for fixable HIGH or CRITICAL findings.
- Related commit: `e751d08` (`ci: add full-stack workflow and image scan`).

---

## Entry 12 - 2026-09-13 18:10-18:17 EEST (15:10-15:17 UTC)

### Symptom and evidence

- Purpose: diagnose the first CI failure, remediate the reported image vulnerabilities, and prove the complete pipeline.
- [CI run #1](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34764720196) for commit `e751d08` failed after 59 seconds at the Trivy image-scan step.
- Trivy found two fixable HIGH vulnerabilities in Debian package `libpcre2-8-0`: `CVE-2026-86145` and `CVE-2026-89161`.
- The image contained version `10.42-1`; Debian provided fixed version `10.42-1+deb12u1`. Because the scan uses `exit-code: "1"`, a fixable HIGH finding correctly failed CI.

### Root cause and fix

- Root cause: the pinned `python:3.12-slim-bookworm` base image still contained the vulnerable PCRE2 package even though its index digest was current.
- Fix: before creating the unprivileged user, the Dockerfile now refreshes Debian package metadata, upgrades only `libpcre2-8-0`, and removes the package lists from the resulting layer.
- The targeted upgrade keeps the security gate enabled instead of hiding the findings or making Trivy non-blocking.

### Retest evidence

- Commit `527f486` (`fix: upgrade vulnerable pcre2 package`) triggered [CI run #2](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34765059184).
- GitHub reports that run #2 completed successfully in 45 seconds, from `2026-09-13 15:15:34 UTC` to `15:16:19 UTC`.
- Checkout, secret-backed `.env` creation, syntax and Compose checks, image build, bounded service startup, full-stack validation, image discovery, Trivy scanning, and cleanup all completed successfully.
- The candidate's investigation and retest window was approximately `18:10-18:17 EEST` / `15:10-15:17 UTC`.

### Conclusion

- The required CI path and optional blocking image scan now pass for commit `527f486`.
- This is pre-video evidence for the current two-app, port-8080 state. The final three-app, port-8090 commit still requires its own matching CI run.
- Related commits: `e751d08` (workflow and initial failed scan) and `527f486` (package remediation and successful pipeline).

---

## Entry 13 - 2026-09-13 18:25-18:52 EEST (15:25-15:52 UTC)

- Purpose: create and document the required final architecture diagram.
- Work began at `2026-09-13 18:25:41 EEST (+0300)` / `15:25:41 UTC` and ended at
  `18:52:04 EEST (+0300)` / `15:52:04 UTC`.
- The diagram records the final client-to-NGINX-to-three-Flask-instance request flow, frontend
  and backend networks, PostgreSQL and Redis ports, named storage, and health/readiness checks.
- `docs/ARCHITECTURE.md` explains that NGINX cannot directly reach the data services and records
  the remaining NGINX, PostgreSQL, Redis, local-volume, and single-host failure points.
- The candidate-created image was placed at the required repository-root path
  `architecture.png`; the assistant did not edit its pixels.
- Related commit: `docs: add final architecture diagram`.
- Remaining evidence: verify the diagram against the live three-app, port-8090 configuration
  during the video and add the real video timestamp to `docs/EVIDENCE_INDEX.md`.

---

## Entry 14 - 2026-09-13 19:01-19:30 EEST (16:01-16:30 UTC)

### Scope and implementation

- Purpose: analyze the three unchanged historical logs and answer all ten questions in
  `log_analysis.md` with reproducible evidence.
- The assistant created `scripts/analyze_logs.py` at the candidate's request using only the Python
  standard library.
- The script parses JSON and NGINX text records, records malformed lines, removes exact/canonical
  duplicates, and treats each access-log `request_id` as one client request so retries are not
  double-counted.
- It produces bounded-width terminal output covering file integrity, final status/error counts,
  paths, backends, incident windows, latency, retries, cross-log correlation, classification, and
  limitations.

### Review and revisions

- The candidate ran and reviewed the output several times and requested multiple changes.
- The first readable-output revision used Markdown tables, which appeared misaligned as literal
  Markdown in the terminal.
- Based on the candidate's screenshots and feedback, the assistant replaced them with aligned ASCII
  tables for compact data and wrapped labeled blocks for wide incident and request evidence.
- The candidate then asked the assistant to use the final output to complete `log_analysis.md`.

### Verification and findings

- `python3 -m py_compile scripts/analyze_logs.py` passed.
- `python3 scripts/analyze_logs.py` completed using all three logs.
- It found 720 distinct requests, 105 final HTTP errors (14.58%), 95 final server errors (13.19%),
  four incident windows, 19 successful retries, 54.0 ms median latency, and 2001.0 ms p95 latency.
- The timeline correlates NGINX connection refusals and timeouts with Redis `TimeoutError`,
  PostgreSQL `InvalidPassword`, and application request events.
- `log_analysis.md` now answers all ten required questions and includes only the output excerpts
  needed to support the results.
- `git diff --check` passed after the documentation updates.
- Related commit: `docs: complete historical log analysis` (the commit containing this work).
- Remaining evidence: demonstrate one historical-log finding during the video and add its real
  timestamp to `docs/EVIDENCE_INDEX.md`.

---

## Blank entry template

Copy this block for each later meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.
