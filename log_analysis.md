# Log analysis

The original files in `logs/` were not modified. All timestamps below are UTC.

## Command

```bash
python3 scripts/analyze_logs.py
```

## Results

### 1. Coverage and file integrity

The access and application logs cover `2026-08-20T11:00:00.015Z` to
`2026-08-20T11:29:57.578Z`. The NGINX error log covers
`2026-08-20T11:05:02.000Z` to `2026-08-20T11:30:00.000Z`.

```text
+-----------------+-------+-------+-----------+------------+
| File            | Total | Valid | Malformed | Duplicates |
+-----------------+-------+-------+-----------+------------+
| access.log      | 726   | 720   | 1         | 5          |
| error.log       | 68    | 68    | 0         | 0          |
| application.log | 730   | 727   | 1         | 2          |
+-----------------+-------+-------+-----------+------------+
```

The malformed entries are access-log line 311 and application-log line 401.
Here, valid means a unique parseable record; duplicates are additional exact or
canonical copies.

### 2. Distinct client requests and deduplication

There were **720 distinct client requests** and no conflicting request IDs. I
deduplicated exact log records first, then counted the final access record for each
`request_id`. Comma-separated upstream attempts and application events are evidence
for the same request, so they were not counted as new client requests.

```text
Distinct request IDs: 720
Conflicting request IDs: 0
```

### 3. Final statuses and error rate

| Final status | Requests |
|---: |---:|
| 200 | 615|
| 404 | 10 |
| 502 | 40 |
| 503 | 47 |
| 504 | 8  |

The denominator is **720 distinct, deduplicated client request IDs**. The total
HTTP error rate (`>=400`) was **105/720 = 14.58%**. The server-error rate (`>=500`)
was **95/720 = 13.19%**.

### 4. Failure paths, windows and backends

| Path | Final 5xx responses |
|---|---:|
| `/` | 10 |
| `/counter` | 26 |
| `/health` | 10 |
| `/ready` | 23 |
| `/records` | 26 |

| Backend | Final 5xx responses |
|---|---:|
| `172.23.0.11:8080` (`app-01`) | 27 |
| `172.23.0.12:8080` (`app-02`) | 68 |

The failures form four windows:

1. `11:05:02.503–11:09:57.503`: 40 HTTP 502 responses across `/`, `/counter`,
   `/health` and `/records`.
2. `11:12:09.525–11:15:52.025`: 31 HTTP 503 responses on `/counter` and `/ready`.
3. `11:20:07.541–11:21:45.041`: 16 HTTP 503 responses on `/ready` and `/records`.
4. `11:25:14.501–11:26:47.001`: 8 HTTP 504 responses on `/records`.

### 5. Client latency

```text
+--------+-----------+-----------------+
| Metric | Value     | Method          |
+--------+-----------+-----------------+
| Median | 54.0 ms   | middle value(s) |
| p95    | 2001.0 ms | nearest rank    |
+--------+-----------+-----------------+
```

`request_time` was converted from seconds to milliseconds. The p95 uses the
nearest-rank method: sorted item `ceil(0.95 × N)`.

### 6. Upstream retries

**19 requests retried upstream, and all 19 ultimately succeeded.** Their IDs are:

```text
lab-000124, lab-000130, lab-000136, lab-000142, lab-000148,
lab-000154, lab-000160, lab-000166, lab-000172, lab-000178,
lab-000184, lab-000190, lab-000196, lab-000202, lab-000208,
lab-000214, lab-000220, lab-000226, lab-000232
```

Each has upstream statuses `502, 200` and final client status `200`.

### 7. Incident timeline across all three logs

| UTC window | Access evidence | NGINX error evidence | Application evidence |
|---|---|---|---|
| `11:05:02.503–11:09:57.503` | 40 × 502 | 59 connection refusals | 77 × 200 and 2 × 404 |
| `11:12:09.525–11:15:52.025` | 31 × 503 | None | 31 Redis `TimeoutError` events and 31 × 503 |
| `11:20:07.541–11:21:45.041` | 16 × 503 | None | 16 PostgreSQL `InvalidPassword` events and 16 × 503 |
| `11:25:14.501–11:26:47.001` | 8 × 504 | 8 upstream timeouts | 38 × 200 and 1 × 404 |

This shows four distinct incidents: app connectivity failure, Redis failure,
PostgreSQL authentication failure, and slow app responses exceeding the NGINX
deadline.

### 8. Correlated request examples

Failed client request:

```text
Access:      2026-08-20T11:25:14.501Z request_id=lab-000606
             path=/records status=504 upstream=172.23.0.12:8080
NGINX:       2026-08-20T11:25:14.000Z request_id=lab-000606
             kind=upstream_timeout
Application: 2026-08-20T11:25:15.200Z request_id=lab-000606
             instance_id=app-02 status=200 duration_ms=2700
```

The application completed after NGINX had already timed out, so the client received
504 even though the app later recorded 200.

Successful request after retry:

```text
Access:      2026-08-20T11:05:07.620Z request_id=lab-000124
             path=/ready upstream_status=502, 200 final_status=200
NGINX:       2026-08-20T11:05:07.000Z request_id=lab-000124
             upstream=172.23.0.12:8080 kind=connection_refused
Application: 2026-08-20T11:05:07.620Z request_id=lab-000124
             instance_id=app-01 status=200 duration_ms=120.0
```

NGINX failed to connect to one backend, retried `app-01`, and returned 200.

### 9. Error classification and proof

| Layer | Signals |
|---|---|
| Proxy/connectivity | 59 `connection_refused`; 8 `upstream_timeout` |
| Dependency/application | 16 PostgreSQL `InvalidPassword`; 31 Redis `TimeoutError` |

`connection_refused` directly proves failed NGINX-to-app connections. For all eight
timeouts, a later app HTTP 200 proves the application finished after the proxy
deadline. The structured application `dependency_error` events explicitly name
PostgreSQL or Redis and their error types.

### 10. Limits and next checks

The logs do not prove which deployment or configuration change initiated each
incident, the state of dependency internals, host resource pressure, or why the
malformed and duplicate lines exist. In a running environment, check only the
relevant Compose/container events and effective configuration, PostgreSQL/Redis
logs and metrics, host resource metrics, and log-collector behavior.

## Conclusion

The dominant failures were backend connectivity and dependency faults. Retries
successfully hid 19 initial backend failures, while PostgreSQL, Redis and slow
application responses produced final client-facing 5xx responses.
