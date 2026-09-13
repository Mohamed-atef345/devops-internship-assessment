#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 BACKUP_FILE" >&2
    exit 2
fi

BACKUP_FILE=$1
if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "FAIL: backup file is missing or empty: $BACKUP_FILE" >&2
    exit 1
fi

docker compose -p barq-assessment exec -T postgres sh -c \
    'psql -X -v ON_ERROR_STOP=1 -1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    < "$BACKUP_FILE"

echo "PASS: backup restored: $BACKUP_FILE"
