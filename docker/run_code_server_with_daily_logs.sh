#!/bin/bash

set -euo pipefail

mkdir -p /app/logs

code-server --bind-addr 0.0.0.0:8080 --auth none /home/coder/workspace \
  > >(awk '{ d=strftime("%Y-%m-%d"); f="/app/logs/code-server-stdout-" d ".log"; print >> f; fflush(f) }') \
  2> >(awk '{ d=strftime("%Y-%m-%d"); f="/app/logs/code-server-stderr-" d ".log"; print >> f; fflush(f) }')
