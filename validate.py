#!/usr/bin/env python3
"""Validate the BARQ API and its Docker Compose topology."""

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


def passed(message):
    print(f"PASS: {message}")


def fail(message):
    print(f"FAIL: {message}")
    raise SystemExit(1)


def run(command, timeout=10):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"could not run {' '.join(command)}: {exc}")


def request_json(base_url, path, expected_status=200, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base_url + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    except urllib.error.URLError as exc:
        fail(f"{method} {path}: {exc}")

    status = response.status
    headers = response.headers
    try:
        body = json.loads(response.read().decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail(f"{method} {path}: response was not valid JSON")

    if status != expected_status:
        fail(f"{method} {path}: expected HTTP {expected_status}, got {status}")
    if not headers.get("X-Request-ID"):
        fail(f"{method} {path}: missing X-Request-ID")
    return body, headers


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--project", default=os.getenv("COMPOSE_PROJECT_NAME", "barq-assessment"))
parser.add_argument("--url", help="public URL; defaults to the running NGINX binding")
parser.add_argument("--timeout", type=float, default=60, help="readiness timeout in seconds")
args = parser.parse_args()
compose = ["docker", "compose", "-p", args.project]

if args.url:
    base_url = args.url.rstrip("/")
else:
    result = run(compose + ["port", "nginx", "80"])
    if result.returncode != 0 or not result.stdout.strip():
        fail("could not discover the NGINX host port")
    try:
        published_port = int(result.stdout.splitlines()[0].rsplit(":", 1)[1])
    except (IndexError, ValueError):
        fail(f"could not parse NGINX binding: {result.stdout.strip()}")
    base_url = f"http://127.0.0.1:{published_port}"

expected_port = urlparse(base_url).port
if expected_port is None:
    parser.error("--url must include a port")

print(f"Validating {base_url} (Compose project: {args.project})")

# wait for real dependency readiness with a fixed overall deadline
deadline = time.monotonic() + args.timeout
while time.monotonic() < deadline:
    try:
        request_timeout = max(0.1, min(3, deadline - time.monotonic()))
        with urllib.request.urlopen(base_url + "/ready", timeout=request_timeout) as response:
            ready = json.loads(response.read().decode())
            dependencies = ready.get("dependencies", {})
            if (response.status == 200 and ready.get("status") == "ready"
                    and dependencies == {"postgres": "ready", "redis": "ready"}):
                break
    except (OSError, ValueError, urllib.error.URLError):
        pass
    time.sleep(min(1, max(0, deadline - time.monotonic())))
else:
    fail(f"dependencies were not ready within {args.timeout:g} seconds")
passed("PostgreSQL and Redis are ready")

# discover configured apps, including any configured app that is currently stopped
result = run(compose + ["config", "--services"])
if result.returncode != 0:
    fail(f"docker compose config failed: {result.stderr.strip()}")
apps = {service for service in result.stdout.splitlines() if service.startswith("app-")}
if not apps:
    fail("no app services are configured")
passed(f"configured backends: {', '.join(sorted(apps))}")

# public API contract
root, _ = request_json(base_url, "/")
if root.get("message") != "Welcome to BARQ Systems":
    fail("GET / returned the wrong message")
passed("GET /")

health, _ = request_json(base_url, "/health")
if health.get("status") != "alive":
    fail("GET /health returned the wrong status")
passed("GET /health")

ready, _ = request_json(base_url, "/ready")
if (ready.get("status") != "ready"
        or ready.get("dependencies") != {"postgres": "ready", "redis": "ready"}):
    fail("GET /ready did not report both dependencies ready")
passed("GET /ready")

title = f"validation-{time.time_ns()}"
created, _ = request_json(base_url, "/records", 201, "POST", {"title": title})
record = created.get("record", {})
if record.get("title") != title or not isinstance(record.get("id"), int):
    fail("POST /records returned an invalid record")
records, _ = request_json(base_url, "/records")
if not any(item.get("id") == record["id"] and item.get("title") == title
           for item in records.get("records", [])):
    fail("GET /records did not contain the created record")
passed("PostgreSQL record creation and retrieval")

request_json(base_url, "/records", 400, "POST", {"title": ""})
passed("invalid record title returns 400")

first, _ = request_json(base_url, "/counter")
second, _ = request_json(base_url, "/counter")
if not (isinstance(first.get("counter"), int)
        and second.get("counter") == first["counter"] + 1):
    fail("GET /counter did not increment by one")
passed(f"Redis counter incremented: {first['counter']} -> {second['counter']}")

request_json(base_url, "/validation-route-does-not-exist", 404)
passed("unknown route returns 404")

# repeated public requests must reach every configured backend
observed = set()
for _ in range(max(20, len(apps) * 10)):
    body, headers = request_json(base_url, "/instance")
    instance = body.get("instance_id")
    if not instance or headers.get("X-Instance-ID") != instance:
        fail("GET /instance header and JSON identity do not match")
    observed.add(instance)
    if apps <= observed:
        break
if not apps <= observed:
    fail(f"expected {sorted(apps)}, observed {sorted(observed)}")
passed(f"observed all backends: {', '.join(sorted(observed))}")

# only NGINX may publish a host port and it must be loopback only
result = run(["docker", "port", "nginx"])
expected_binding = f"80/tcp -> 127.0.0.1:{expected_port}"
if result.returncode != 0 or result.stdout.strip() != expected_binding:
    fail(f"expected NGINX binding {expected_binding!r}, got {result.stdout.strip()!r}")
for container in ["postgres", "redis", *sorted(apps)]:
    result = run(["docker", "port", container])
    if result.returncode != 0:
        fail(f"could not inspect ports for {container}")
    if result.stdout.strip():
        fail(f"{container} publishes a prohibited host port: {result.stdout.strip()}")
passed(f"only NGINX publishes {expected_binding}")

# enforce the required two network topology
def networks(container):
    result = run([
        "docker", "inspect", "--format",
        "{{json .NetworkSettings.Networks}}", container,
    ])
    if result.returncode != 0:
        fail(f"could not inspect networks for {container}")
    try:
        names = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f"invalid network inspection output for {container}")
    return {name.rsplit("_", 1)[-1] for name in names}


expected_networks = {
    "nginx": {"frontend"},
    "postgres": {"backend"},
    "redis": {"backend"},
    **{app: {"frontend", "backend"} for app in apps},
}
for container, expected in expected_networks.items():
    actual = networks(container)
    if actual != expected:
        fail(f"{container} networks: expected {sorted(expected)}, got {sorted(actual)}")
passed("network isolation")

print("ALL VALIDATION CHECKS PASSED")
