#!/usr/bin/env bash
# Run the Briefd scheduler — meant to be called hourly by cron or Fly Machines.
# Reads BRIEFD_USERS env var: comma-separated user:topics:hour triples.
# Example: BRIEFD_USERS="alice@x.com:python,rust:7,bob@x.com:llm:8"

set -euo pipefail

DB="${BRIEFD_DB:-/data/briefd.db}"
USERS="${BRIEFD_USERS:-}"

if [[ -z "$USERS" ]]; then
  echo "BRIEFD_USERS not set — nothing to schedule"
  exit 0
fi

# Build --user args from comma-separated triples
USER_ARGS=()
IFS=',' read -ra PARTS <<< "$USERS"
i=0
while [[ $i -lt ${#PARTS[@]} ]]; do
  uid="${PARTS[$i]}"
  topics="${PARTS[$((i+1))]}"
  hour="${PARTS[$((i+2))]}"
  USER_ARGS+=("--user" "${uid}:${topics}:${hour}")
  i=$((i+3))
done

exec uv run briefd schedule --db "$DB" "${USER_ARGS[@]}"
