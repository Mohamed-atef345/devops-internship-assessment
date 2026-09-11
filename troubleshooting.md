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
