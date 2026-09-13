#!/usr/bin/env bash
set -euo pipefail

OUTPUT=${1:-"backups/barq-tasks-$(date -u +%Y%m%dT%H%M%SZ).sql"}
TEMP_FILE="${OUTPUT}.tmp"

mkdir -p "$(dirname "$OUTPUT")"
trap 'rm -f -- "$TEMP_FILE"' EXIT

docker compose -p barq-assessment exec -T postgres sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
    > "$TEMP_FILE"

if [[ ! -s "$TEMP_FILE" ]]; then
    echo "FAIL: backup is empty" >&2
    exit 1
fi

mv "$TEMP_FILE" "$OUTPUT"
trap - EXIT
echo "PASS: backup created: $OUTPUT"
