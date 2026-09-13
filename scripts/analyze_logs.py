#!/usr/bin/env python3
"""Analyze the three supplied BARQ incident logs with no external dependencies."""

import json
import math
import re
import statistics
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
ACCESS_FIELDS = {
    "timestamp", "request_id", "method", "path", "status", "upstream",
    "upstream_status", "request_time",
}
ERROR_LINE = re.compile(
    r"^(?P<date>\d{4}/\d{2}/\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>\w+)\] (?P<message>.+)$"
)
OUTPUT_WIDTH = 100


def iso_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_time(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def compact(counter):
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter, key=str)) or "none"


def title(value):
    print(value)
    print("=" * len(value))


def section(number, value):
    heading = f"{number}. {value.upper()}"
    print(f"\n{heading}")
    print("-" * len(heading))


def subsection(value):
    print(f"\n{value}")
    print("~" * len(value))


def detail(label, value, indent=2):
    prefix = " " * indent + f"{label}: "
    print(textwrap.fill(
        str(value), width=OUTPUT_WIDTH, initial_indent=prefix,
        subsequent_indent=" " * len(prefix), break_long_words=False,
        break_on_hyphens=False,
    ))


def bullet(value):
    print(textwrap.fill(
        str(value), width=OUTPUT_WIDTH, initial_indent="  - ",
        subsequent_indent="    ", break_long_words=False, break_on_hyphens=False,
    ))


def table(headers, rows):
    """Print a bordered, wrapped table no wider than OUTPUT_WIDTH."""
    headers = tuple(str(value) for value in headers)
    rows = [tuple(str(value) for value in row) for row in rows]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], max(map(len, value.splitlines()), default=0))

    overhead = 3 * len(headers) + 1
    minimums = [max(len(header), 6) for header in headers]
    while sum(widths) + overhead > OUTPUT_WIDTH:
        candidates = [i for i, width in enumerate(widths) if width > minimums[i]]
        if not candidates:
            break
        widest = max(candidates, key=lambda i: widths[i] - minimums[i])
        widths[widest] -= 1

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def print_row(row):
        wrapped = [
            textwrap.wrap(value, width=width, break_long_words=False,
                          break_on_hyphens=False) or [""]
            for value, width in zip(row, widths)
        ]
        for line_number in range(max(map(len, wrapped))):
            cells = [
                lines[line_number] if line_number < len(lines) else ""
                for lines in wrapped
            ]
            print("| " + " | ".join(
                value.ljust(width) for value, width in zip(cells, widths)
            ) + " |")

    print(border)
    print_row(headers)
    print(border)
    for row in rows:
        print_row(row)
    print(border)


def load_json_lines(name, required):
    path = LOGS / name
    records, malformed, seen, duplicates = [], [], set(), 0
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or not required <= record.keys():
                raise ValueError("missing required fields")
            record["_time"] = iso_time(record["timestamp"])
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            malformed.append((number, str(exc)))
            continue
        key = json.dumps({k: v for k, v in record.items() if k != "_time"},
                         sort_keys=True, separators=(",", ":"))
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        records.append(record)
    return {
        "name": name, "total": len(lines), "records": records,
        "malformed": malformed, "duplicates": duplicates,
    }


def load_error_log():
    path = LOGS / "error.log"
    records, malformed, seen, duplicates = [], [], set(), 0
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        match = ERROR_LINE.match(line)
        if not match:
            malformed.append((number, "unrecognized NGINX log format"))
            continue
        if line in seen:
            duplicates += 1
            continue
        seen.add(line)
        record = match.groupdict()
        record["_time"] = datetime.strptime(
            f"{record['date']} {record['time']}", "%Y/%m/%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        message = record["message"]
        request_id = re.search(r"request_id=([^,\s]+)", message)
        request = re.search(r'request: "(\S+) (\S+) [^"]+"', message)
        upstream = re.search(r'upstream: "https?://([^/"]+)', message)
        record["request_id"] = request_id.group(1) if request_id else None
        record["method"] = request.group(1) if request else None
        record["path"] = request.group(2) if request else None
        record["upstream"] = upstream.group(1) if upstream else None
        if "connect() failed" in message:
            record["kind"] = "connection_refused"
        elif "upstream timed out" in message:
            record["kind"] = "upstream_timeout"
        elif record["level"] == "notice":
            record["kind"] = "notice"
        else:
            record["kind"] = "other"
        records.append(record)
    return {
        "name": "error.log", "total": len(lines), "records": records,
        "malformed": malformed, "duplicates": duplicates,
    }


def unique_requests(access):
    grouped = defaultdict(list)
    for record in access:
        grouped[record["request_id"]].append(record)
    conflicts = {key: rows for key, rows in grouped.items() if len(rows) > 1}
    final = [max(rows, key=lambda row: row["_time"]) for rows in grouped.values()]
    return sorted(final, key=lambda row: row["_time"]), conflicts


def percentile_nearest_rank(values, percentile):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def split_values(value):
    return [item.strip() for item in str(value).split(",") if item.strip()]


def incident_windows(failures, gap_seconds=90):
    windows = []
    for record in failures:
        if not windows or (record["_time"] - windows[-1][-1]["_time"]).total_seconds() > gap_seconds:
            windows.append([record])
        else:
            windows[-1].append(record)
    return windows


def record_summary(record):
    if not record:
        return "none"
    fields = [fmt_time(record["_time"]), f"request_id={record.get('request_id')}"]
    for key in ("path", "status", "upstream", "upstream_status", "instance_id",
                "event", "kind", "dependency", "error_type", "duration_ms"):
        if record.get(key) is not None:
            fields.append(f"{key}={record[key]}")
    return " ".join(fields)


def main():
    access_data = load_json_lines("access.log", ACCESS_FIELDS)
    app_data = load_json_lines("application.log", {"timestamp", "event", "request_id"})
    error_data = load_error_log()
    datasets = [access_data, error_data, app_data]
    access, conflicts = unique_requests(access_data["records"])
    app, errors = app_data["records"], error_data["records"]

    title("BARQ HISTORICAL LOG ANALYSIS")
    detail("Command", "python3 scripts/analyze_logs.py")
    section(1, "UTC coverage and file integrity")
    bullet("Valid = unique parseable record. Duplicate = extra exact/canonical copy.")
    integrity_rows = []
    for data in datasets:
        times = [row["_time"] for row in data["records"]]
        integrity_rows.append((
            data["name"], data["total"], len(data["records"]),
            len(data["malformed"]), data["duplicates"],
        ))
    table(("File", "Total", "Valid", "Malformed", "Duplicates"), integrity_rows)
    subsection("UTC coverage")
    for data in datasets:
        times = [row["_time"] for row in data["records"]]
        detail(data["name"], f"{fmt_time(min(times))} to {fmt_time(max(times))}")
    for data in datasets:
        if data["malformed"]:
            detail(f"{data['name']} malformed lines",
                   ", ".join(str(row[0]) for row in data["malformed"]))

    section(2, "Distinct client requests and deduplication")
    detail("Distinct request IDs", len(access))
    detail("Conflicting request IDs", len(conflicts))
    bullet("Deduplication key: access-log request_id. Application events and NGINX "
           "upstream attempts are supporting evidence, not additional client requests.")

    statuses = Counter(row["status"] for row in access)
    client_errors = sum(count for status, count in statuses.items() if 400 <= status < 500)
    server_errors = sum(count for status, count in statuses.items() if status >= 500)
    all_errors = client_errors + server_errors
    denominator = len(access)
    section(3, "Final client statuses and error rates")
    table(("Final HTTP status", "Requests"), sorted(statuses.items()))
    detail("HTTP >=400 error rate",
           f"{all_errors}/{denominator} ({100 * all_errors / denominator:.2f}%)")
    detail("HTTP >=500 server-error rate",
           f"{server_errors}/{denominator} ({100 * server_errors / denominator:.2f}%)")
    detail("Denominator", "distinct deduplicated client request IDs from access.log")

    app_by_id = defaultdict(list)
    for row in app:
        app_by_id[row["request_id"]].append(row)
    address_votes = defaultdict(Counter)
    for row in access:
        http_rows = [event for event in app_by_id.get(row["request_id"], [])
                     if event.get("event") == "http_request"]
        if http_rows:
            address_votes[split_values(row["upstream"])[-1]][http_rows[-1].get("instance_id")] += 1
    address_map = {address: votes.most_common(1)[0][0]
                   for address, votes in address_votes.items() if votes}
    failures = [row for row in access if row["status"] >= 500]
    failure_paths = Counter(row["path"] for row in failures)
    failure_backends = Counter(
        f"{address} ({address_map.get(address, 'unknown')})"
        for row in failures for address in [split_values(row["upstream"])[-1]]
    )
    section(4, "Final 5xx failures by path, window, and backend")
    subsection("Paths")
    table(("Path", "Final 5xx responses"), sorted(failure_paths.items()))
    subsection("Backends")
    table(("Upstream", "Final 5xx responses"), sorted(failure_backends.items()))
    subsection("Incident windows")
    windows = incident_windows(failures)
    for number, window in enumerate(windows, 1):
        print(f"\n  Incident {number}")
        detail("UTC interval",
               f"{fmt_time(window[0]['_time'])} to {fmt_time(window[-1]['_time'])}", 4)
        detail("Final 5xx", len(window), 4)
        detail("Statuses", compact(Counter(r["status"] for r in window)), 4)
        detail("Paths", compact(Counter(r["path"] for r in window)), 4)

    latencies = [float(row["request_time"]) * 1000 for row in access]
    section(5, "Client latency")
    table(("Metric", "Value", "Method"), (
        ("Median", f"{statistics.median(latencies):.1f} ms", "middle value(s)"),
        ("p95", f"{percentile_nearest_rank(latencies, 0.95):.1f} ms", "nearest rank"),
    ))

    retries = [row for row in access if len(split_values(row["upstream_status"])) > 1]
    retry_successes = [row for row in retries if row["status"] < 500]
    section(6, "Upstream retries")
    detail("Retried client requests", len(retries))
    detail("Successful after retry", len(retry_successes))
    table(("Request ID", "Upstream statuses", "Final status"), (
        (row["request_id"], row["upstream_status"], row["status"]) for row in retries
    ))

    section(7, "Incident timeline correlated across all three logs")
    for number, window in enumerate(windows, 1):
        start, end = window[0]["_time"], window[-1]["_time"]
        boundary_start, boundary_end = start - timedelta(seconds=1), end + timedelta(seconds=1)
        related_errors = [row for row in errors if boundary_start <= row["_time"] <= boundary_end]
        related_app = [row for row in app if boundary_start <= row["_time"] <= boundary_end]
        app_signals = Counter(
            f"dependency:{row.get('dependency')}:{row.get('error_type')}"
            if row.get("event") == "dependency_error"
            else f"http:{row.get('status')}"
            for row in related_app
        )
        print(f"\n  Incident {number}")
        detail("UTC interval", f"{fmt_time(start)} to {fmt_time(end)}", 4)
        detail("Access", compact(Counter(r["status"] for r in window)), 4)
        detail("NGINX", compact(Counter(r["kind"] for r in related_errors)), 4)
        detail("Application", compact(app_signals), 4)

    error_by_id = defaultdict(list)
    for row in errors:
        if row.get("request_id"):
            error_by_id[row["request_id"]].append(row)
    failed_example = next(
        (row for row in failures if error_by_id.get(row["request_id"])
         and app_by_id.get(row["request_id"])), failures[0]
    )
    success_example = next(row for row in retry_successes if row["request_id"] in error_by_id)
    section(8, "Correlated examples")
    subsection("Failed client request")
    detail("Access", record_summary(failed_example))
    detail("NGINX", record_summary(error_by_id[failed_example["request_id"]][0]))
    for row in app_by_id.get(failed_example["request_id"], []):
        detail("Application", record_summary(row))
    subsection("Successful client request after retry")
    detail("Access", record_summary(success_example))
    detail("NGINX", record_summary(error_by_id[success_example["request_id"]][0]))
    for row in app_by_id.get(success_example["request_id"], []):
        detail("Application", record_summary(row))

    dependency_errors = [row for row in app if row.get("event") == "dependency_error"]
    nginx_kinds = Counter(row["kind"] for row in errors if row["kind"] != "notice")
    dependency_kinds = Counter(
        f"{row.get('dependency')}:{row.get('error_type')}" for row in dependency_errors
    )
    slow_after_timeout = sum(
        1 for row in errors if row["kind"] == "upstream_timeout"
        and any(event.get("event") == "http_request" and event.get("status") == 200
                for event in app_by_id.get(row.get("request_id"), []))
    )
    section(9, "Error classification and proof")
    table(("Layer", "Signals"), (
        ("NGINX/proxy", compact(nginx_kinds)),
        ("Application dependencies", compact(dependency_kinds)),
    ))
    bullet(f"{slow_after_timeout} upstream timeouts have a later app HTTP 200, proving that "
           "the app completed after the proxy deadline.")
    bullet("connection_refused proves failed NGINX-to-app connections.")
    bullet("Application dependency_error events directly identify PostgreSQL and Redis failures.")

    section(10, "Limits and next checks")
    bullet("The logs do not prove the deployment/configuration change that started each incident, "
           "host resource pressure, dependency internals, or why duplicate/malformed lines exist.")
    bullet("Next checks: Compose/container events and effective configuration; PostgreSQL and Redis "
           "logs/metrics; host CPU, memory, disk, and network metrics; and collector behavior.")


if __name__ == "__main__":
    main()
