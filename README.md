<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# BARQ DevOps Assessment

Docker Compose deployment of a Flask API behind NGINX with PostgreSQL and Redis.
The checked-in pre-video state runs two application instances on public loopback port
`8080`. During the required recording, it will be changed live to three instances and
port `8090`; the final commit and this status must then be updated to match.

## Architecture

```text
Client -> NGINX -> app-01 / app-02 /app-03
                         |-> PostgreSQL
                         `-> Redis
```

- Only NGINX publishes a host port, bound to `127.0.0.1`.
- NGINX and the apps share `frontend`; the apps and data services share the internal
  `backend`. NGINX cannot directly reach PostgreSQL or Redis.
- Apps listen on port `8080`, PostgreSQL on `5432`, and Redis on `6379` inside Docker.
- PostgreSQL uses `postgres-data`; Redis uses AOF on `redis-data`.
- The [architecture diagram](architecture.png) and
  [architecture notes](docs/ARCHITECTURE.md) show the required final three-app/port-8090 state.

## Requirements

- Linux or WSL2
- Git, Docker Engine and Docker Compose
- Python 3.12
- `curl` and `jq`
- Internet access for the initial image build

## Configuration

Create the ignored runtime environment file once:

```bash
test -f .env || cp .env.example .env
chmod 600 .env
```

Edit `.env` and replace only `POSTGRES_PASSWORD` with a synthetic local lab password.
Do not print or commit `.env`. The safe variable names and defaults remain in
[.env.example](.env.example).

## Build and start

```bash
docker compose -p barq-assessment config -q
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps
```

Discover the active loopback URL instead of hard-coding the port:

```bash
export PUBLIC_URL="http://$(docker compose -p barq-assessment port nginx 80)"
printf '%s\n' "$PUBLIC_URL"
```

All services should be running and healthy before testing.

## API checks

```bash
curl -fsS "$PUBLIC_URL/" | jq
curl -fsS "$PUBLIC_URL/health" | jq
curl -fsS "$PUBLIC_URL/ready" | jq
curl -fsS "$PUBLIC_URL/instance" | jq

curl -fsS -X POST "$PUBLIC_URL/records" \
  -H 'Content-Type: application/json' \
  -d '{"title":"README verification"}' | jq

curl -fsS "$PUBLIC_URL/records" | jq
curl -fsS "$PUBLIC_URL/counter" | jq
```

`/health` is application liveness and does not query dependencies. `/ready` returns
HTTP 200 only when both PostgreSQL and Redis respond. Repeated `/instance` calls prove
that NGINX reaches every configured backend:

```bash
for _ in {1..20}; do
  curl -fsS "$PUBLIC_URL/instance" | jq -r '.instance_id'
done | sort | uniq -c
```

## Tests and validation

Run the eight app-only unit tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
deactivate
```

Run the complete environment validator:

```bash
python3 validate.py
```

Validation uses bounded waits and exits non-zero if readiness, an endpoint, a real
PostgreSQL/Redis operation, a configured backend, host-port isolation, or network
membership is wrong. It creates one uniquely named database record and increments the
Redis counter twice.

## Backend failure and recovery

This test stops `app-01`, measures 20 public requests, restores it through an exit trap,
and proves that the recovered backend serves again:

```bash
./failure_test.sh
```

The test is intentionally disruptive to one app container. Run it only against this local
assessment stack.

## Persistence test

The following creates a PostgreSQL record, recreates PostgreSQL and every configured app
without removing volumes, restarts NGINX to refresh upstream resolution, and proves the
record survived:

```bash
export PERSISTENCE_TITLE="persistence-$(date -u +%Y%m%dT%H%M%SZ)"
CREATE_RESPONSE=$(curl -fsS -X POST "$PUBLIC_URL/records" \
  -H 'Content-Type: application/json' \
  -d "{\"title\":\"$PERSISTENCE_TITLE\"}")
export PERSISTENCE_ID=$(jq -r '.record.id' <<<"$CREATE_RESPONSE")
printf '%s\n' "$CREATE_RESPONSE" | jq

APP_SERVICES=($(docker compose -p barq-assessment config --services | awk '/^app-/'))
docker compose -p barq-assessment up -d --force-recreate postgres "${APP_SERVICES[@]}"
docker compose -p barq-assessment restart nginx

until curl -fsS "$PUBLIC_URL/ready" >/dev/null; do sleep 2; done
curl -fsS "$PUBLIC_URL/records" |
  jq --argjson id "$PERSISTENCE_ID" '.records[] | select(.id == $id)'
```

Do not use `down --volumes` during a persistence test.

## PostgreSQL backup and restore

Create a non-empty logical SQL backup in the ignored `backups/` directory:

```bash
BACKUP_FILE="backups/barq-tasks-$(date -u +%Y%m%dT%H%M%SZ).sql"
./backup.sh "$BACKUP_FILE"
test -s "$BACKUP_FILE" && echo "PASS: backup is non-empty"
```

Restore replaces the current database objects and data with the selected snapshot:

```bash
./restore.sh "$BACKUP_FILE"
curl -fsS "$PUBLIC_URL/ready" | jq
python3 validate.py
```

Named volumes provide container-recreation persistence, not an off-host backup. Production
backups should be encrypted, access-controlled, retained off-host, monitored, and restore-tested.

## Historical log analysis

The original files in `logs/` are unchanged. Run:

```bash
python3 scripts/analyze_logs.py
```

The [completed report](log_analysis.md) answers all ten questions with counts, latency,
incident windows, retry handling, and request-level correlation across access, NGINX error,
and application logs. Client requests are counted by deduplicated access-log `request_id`,
so internal upstream retries are not counted twice.

## Continuous integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs for pushes and pull requests
targeting `main`. Configure the repository Actions secret `POSTGRES_PASSWORD` before
running it. One job performs:

```text
checkout -> syntax/Compose checks -> build -> start -> bounded readiness ->
full-stack validation -> Trivy image scan -> cleanup
```

Cleanup runs even after failure and removes only the disposable CI project's containers,
networks, and volumes. The Trivy gate fails on fixable HIGH or CRITICAL findings. No
deployment stage exists because this assessment has no authorized deployment target.

The initial Trivy run found two HIGH PCRE2 findings. Commit `527f486` upgraded the affected
package, and the [complete retest passed](https://github.com/Mohamed-atef345/devops-internship-assessment/actions/runs/34765059184).
A green run proves the checked revision passed the encoded checks in that runner environment;
it does not prove production capacity, external availability, backup retention, or the absence
of every vulnerability.

## Design rationale and limitations

- The first public failure was an NGINX port mismatch. Testing container ports 81 and 80
  separated that failure from the later upstream 502 and exposed the next fault layer.
- NGINX retries only connection, timeout, 502, and 504 failures, with two attempts and a
  four-second overall retry bound. This supports one-app failure without unlimited delay.
- `unless-stopped` allows unexpected process recovery while respecting deliberate stops.
  CPU and memory limits prevent one service from consuming the whole assessment host.
- The apps run as an unprivileged numeric user under Gunicorn. Image references are pinned,
  while a targeted Debian package upgrade addresses the detected PCRE2 vulnerabilities.
- Three final app instances improve application-tier availability, but NGINX, PostgreSQL,
  Redis, local volumes, and the Docker host remain single points of failure. Production would
  require redundant ingress, replicated data services, and storage independent of one host.
- Further production work includes centralized metrics/logging, alerting, secret management,
  encrypted off-host backups, restore drills, load testing, and orchestrator-native probes.

Detailed evidence and trade-offs are recorded in:

- [Troubleshooting journal](troubleshooting.md)
- [Technical decisions](decisions.md)
- [Security and production-readiness review](security_review.md)
- [AI usage disclosure](AI_USAGE.md)
- [Evidence index](docs/EVIDENCE_INDEX.md)

## Recorded challenge

Run `./video_challenge.sh` exactly once in this working copy and only during the continuous
12–18 minute video. Diagnose and repair its single runtime fault without
`docker compose down`. Afterward, record its ignored receipt ID in the evidence index.

there is now 3 app containers and they run on port 8090

## Stop and cleanup

Stop containers while preserving them and their data:

```bash
docker compose -p barq-assessment stop
```

Remove this project's containers and networks while preserving named volumes:

```bash
docker compose -p barq-assessment down --remove-orphans
```

Removing `postgres-data` or `redis-data` destroys the corresponding local state. Never use
global Docker prune commands for this assessment.
