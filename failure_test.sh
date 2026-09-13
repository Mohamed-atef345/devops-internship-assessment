#!/usr/bin/env bash

set -euo pipefail

BINDING=$(docker compose -p barq-assessment port nginx 80)
PORT=${BINDING##*:}
BASE_URL="http://127.0.0.1:$PORT"

# check that app-01 is running
if ! docker compose -p barq-assessment ps --format "{{.Name}}" | grep -qx "app-01"; then
  echo "FAIL: app-01 is not running"
  exit 1
else
    echo "PASS: app-01 is running"
fi
# confirm that at least 2 app containers are running 
APP_CONTAINERS_COUNT=$(docker compose -p barq-assessment ps --format "{{.Name}}" | grep -c '^app-' || true)
if [[ $APP_CONTAINERS_COUNT -lt 2 ]]; then
  echo "FAIL: fewer than 2 app containers are running"
  exit 1
else
    echo "PASS: $APP_CONTAINERS_COUNT app containers are running"
fi
# confirm that /ready responds with 200 before running the test
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${BASE_URL}/ready" || true)
if [[ $STATUS != 200 ]]; then
    echo "FAIL: /ready did not respond with 200"
    exit 1
else
    echo "PASS: /ready responded with 200"
fi

stopped=false
cleanup() {
    if [[ "$stopped" == true ]]; then
        echo "Restoring app-01..."
        docker compose -p barq-assessment start app-01 > /dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# stop app-01
echo "Stopping app-01..."
if docker compose -p barq-assessment stop app-01 > /dev/null 2>&1; then
    stopped=true
    echo "PASS: stopped app-01"
else
    echo "FAIL: could not stop app-01"
    exit 1
fi

# send 20 requests to /instance and check the response
success_count=0
failure_count=0
BACKEND=""
for i in {1..20}; do
    if RESPONSE=$(curl -fsS --max-time 3 "${BASE_URL}/instance"); then
        STATUS=$(jq -r '.status // empty' <<<"$RESPONSE" 2>/dev/null || true)
        BACKEND=$(jq -r '.instance_id // empty' <<<"$RESPONSE" 2>/dev/null || true)

        if [[ "$STATUS" == "ok" && -n "$BACKEND" && "$BACKEND" != "app-01" ]]; then
            success_count=$((success_count + 1))
        else
            failure_count=$((failure_count + 1))
        fi
    else
        failure_count=$((failure_count + 1))
    fi
done
echo "Successes: $success_count"
echo "Failures: $failure_count"
echo "observed_app: $BACKEND"

if [[ $success_count == 20 ]]; then
    echo "PASS: service remained available"
else
    echo "FAIL: service was disrupted"
    exit 1
fi

# restart app-01
echo "Restarting app-01..."
if docker compose -p barq-assessment start app-01 > /dev/null 2>&1; then
    stopped=false
    echo "PASS: restarted app-01"
else
    echo "FAIL: could not restart app-01"
    exit 1
fi

# send traffic and watch until app-01 resumes serving traffic
app01_recovered=false
for i in {1..30}; do
    if RESPONSE=$(curl -fsS --max-time 3 "${BASE_URL}/instance" 2>/dev/null); then
        BACKEND=$(jq -r '.instance_id // empty' <<<"$RESPONSE" 2>/dev/null || true)

        if [[ "$BACKEND" == "app-01" ]]; then
            app01_recovered=true
            echo "PASS: app-01 served traffic again"
            break
        fi
    fi
    sleep 1
done
if [[ "$app01_recovered" != true ]]; then
    echo "FAIL: app-01 did not resume serving traffic within timeout"
    exit 1
fi

echo "ALL FAILURE TESTS PASSED" 
