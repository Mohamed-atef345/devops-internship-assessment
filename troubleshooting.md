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
