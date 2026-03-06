#!/usr/bin/env bash
# Run the Briefd scheduler — call hourly from cron or Fly Machines.
# Reads all registered users from the briefd DB automatically.
# Uses BRIEFD_DB env var (default: /data/briefd.db).

set -euo pipefail

DB="${BRIEFD_DB:-/data/briefd.db}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] briefd schedule --db $DB"
exec uv run briefd schedule --db "$DB"
