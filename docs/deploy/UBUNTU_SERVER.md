# Ubuntu Server Deployment

This document describes how to run this repository on a standalone Ubuntu server using Docker Compose, without Azure.

## Overview

- You deploy the same `docker/docker-compose.yml`, plus a small Ubuntu override file: `docker/docker-compose.ubuntu.yml`.
- The Ubuntu override swaps the app entrypoint to `ubuntu_start.sh`, which sources `.env` and `.env.secrets` from a host directory.

## Prerequisites

- Ubuntu 24.04 LTS (recommended)
- Docker Engine + Docker Compose plugin (`docker compose`)
- SSH access to the server (key-based auth recommended)
- `rsync` installed locally and on the server

## Entrypoint: ubuntu_start.sh

The image includes `/usr/local/bin/ubuntu_start.sh`. On Ubuntu deployments, the compose override sets:

- `entrypoint: ["/usr/local/bin/ubuntu_start.sh"]`
- `command: ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]`

The script reads:

- `${ENV_DIR:-/opt/app}/.env`
- `${ENV_DIR:-/opt/app}/.env.secrets` (optional)

## First Deploy (SSH)

Use the Ubuntu deploy engine:

```bash
source .venv/bin/activate
python scripts/deploy/ubuntu_deploy.py \
  --host user@your-server \
  --remote-dir /opt/protected-container \
  --sync-secrets
```

This copies:

- `docker/docker-compose.yml`
- `docker/docker-compose.ubuntu.yml`
- `docker/`
- optionally `.env` + `.env.secrets`

Then runs `docker compose pull` and `docker compose up -d` on the server.

## Updating

Re-run the deploy command after pushing a new image or changing compose configuration.

## Notes

- For multi-app servers, you typically want a single shared Caddy instance bound to 80/443, and each app stack runs without its own Caddy sidecar.

### Multi-app: Shared Caddy Pattern

The default compose in this repo is **one Caddy per stack** (good for a single-app server). For multi-app, use the provided override:

- [docker/docker-compose.shared-caddy.yml](../../docker/docker-compose.shared-caddy.yml)

This override:

- Adds the app stack to an external Docker network named `caddy`.
- Puts the repo’s `caddy` sidecar behind a non-default profile so it does **not** start unless explicitly enabled.

On the server, create the shared network once:

```bash
docker network create caddy
```

Then deploy the app stack using the extra override file:

```bash
python scripts/deploy/ubuntu_deploy.py \
  --host user@your-server \
  --remote-dir /opt/protected-container \
  --compose-files docker/docker-compose.yml,docker/docker-compose.ubuntu.yml,docker/docker-compose.shared-caddy.yml
```

For the shared Caddy instance itself, use a Caddyfile that contains *multiple* host blocks, for example:

- [docker/Caddyfile.multiapp.example](../../docker/Caddyfile.multiapp.example)
