#!/bin/bash

set -euo pipefail

mkdir -p /app/logs

ensure_daily_files() {
  local current_date=""
  while true; do
    local date_now
    date_now="$(date +%Y-%m-%d)"
    if [ "$date_now" != "$current_date" ]; then
      touch "/app/logs/code-server-stdout-${date_now}.log"
      touch "/app/logs/code-server-stderr-${date_now}.log"
      current_date="$date_now"
    fi
    sleep 60
  done
}

ensure_daily_files &
DATE_WATCHER_PID=$!

cleanup() {
  kill "$DATE_WATCHER_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

code-server --bind-addr 0.0.0.0:8080 --auth none /home/coder/workspace \
  > >(awk '{ d=strftime("%Y-%m-%d"); f="/app/logs/code-server-stdout-" d ".log"; print >> f; fflush(f) }') \
  2> >(awk '{ d=strftime("%Y-%m-%d"); f="/app/logs/code-server-stderr-" d ".log"; print >> f; fflush(f) }')
