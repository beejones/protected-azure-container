# Storage Manager

The Storage Manager is a lightweight service that monitors Docker volume paths and applies cleanup rules automatically.

This document is the operational guide for other apps that want automatic cleanup in this shared host setup.

## What is implemented

- Containerized service scaffold under `docker/storage-manager/`
- Flask API endpoints:
  - `POST /api/register`
  - `DELETE /api/register/{volume}/{path}`
  - `GET /api/volumes`
  - `GET /api/health`
- SQLite-backed registration persistence
- Three cleanup algorithms:
  - `max_size`
  - `remove_before_date`
  - `keep_n_latest`
- APScheduler-based periodic cleanup runner
- Ubuntu deploy integration:
  - `scripts/deploy/ubuntu_deploy.py` parses `storage-manager.*` compose labels
  - registrations are auto-posted to Storage Manager when `STORAGE_MANAGER_API_URL` is configured

## Required host mounts

The storage-manager container must have both mounts:

- `/var/run/docker.sock:/var/run/docker.sock:ro` (Docker API discovery)
- `/var/lib/docker/volumes:/var/lib/docker/volumes:ro` (read volume paths for usage metrics and cleanup)

Without the `/var/lib/docker/volumes` mount, `/api/volumes` may show `current_bytes: 0` and cleanup jobs cannot inspect target files.

## Compose label format

Use indexed labels to register one or more targets on a service:

```yaml
services:
  app:
    labels:
      storage-manager.0.volume: "${COMPOSE_PROJECT_NAME:-docker}_logs"
      storage-manager.0.path: "/"
      storage-manager.0.algorithm: "remove_before_date"
      storage-manager.0.max_age_days: "2"
      storage-manager.0.description: "Rotate code-server logs, keep last 2 days"
```

## How other apps should integrate

### 1) Mount a named volume in your app

Example:

```yaml
services:
  my-app:
    volumes:
      - my-app-data:/app/data

volumes:
  my-app-data:
```

### 2) Add storage-manager labels on that service

Example:

```yaml
services:
  my-app:
    volumes:
      - my-app-data:/app/data
    labels:
      storage-manager.0.volume: "my-app-data"
      storage-manager.0.path: "/"
      storage-manager.0.algorithm: "remove_before_date"
      storage-manager.0.max_age_days: "7"
      storage-manager.0.description: "Keep 7 days of app data"
```

For multiple targets, use `storage-manager.1.*`, `storage-manager.2.*`, etc.

### 3) Deploy with ubuntu_deploy

`scripts/deploy/ubuntu_deploy.py` reads compose labels and handles registration.

- If `STORAGE_MANAGER_API_URL` is set, labels are posted directly via API.
- If `STORAGE_MANAGER_API_URL` is not set but `storage-manager` is in the same stack, Docker label auto-discovery is used automatically.

### 4) Verify registration

After deploy:

- `https://storage.zenia.eu/api/health`
- `https://storage.zenia.eu/api/volumes`

Your target volume should appear in `registrations`.

## Label reference

Required label keys per index:

- `storage-manager.<n>.volume`
- `storage-manager.<n>.path`
- `storage-manager.<n>.algorithm`

Optional keys:

- `storage-manager.<n>.description`
- algorithm-specific params like `max_age_days`, `max_bytes`, `keep_count`, `sort_by`

Path semantics:

- `"/"` means the full volume root.
- subpaths like `"/recordings"` scope cleanup to that directory.

Supported algorithms:

- `remove_before_date` (`max_age_days` or `before_date`)
- `max_size` (`max_bytes`, optional `sort_by`)
- `keep_n_latest` (`keep_count`, optional `sort_by`)

## Environment variables

Runtime (`env.example`):

- `SM_CHECK_INTERVAL_SECONDS=300`
- `SM_LOG_LEVEL=INFO`
- `SM_DB_PATH=/data/storage_manager.db`
- `SM_API_PORT=9100`

Deploy-time (`env.deploy.example`):

- `STORAGE_MANAGER_API_URL=https://storage.your-domain.com`
- `STORAGE_MANAGER_IMAGE=ghcr.io/your-user/protected-container-storage-manager:latest`
- `STORAGE_MANAGER_DOCKERFILE=docker/storage-manager/Dockerfile`

## Run locally

```bash
docker compose -f docker/storage-manager/docker-compose.yml up --build
```

The API will listen on container port `9100` and can be routed via centralized Caddy.

## Troubleshooting

- `ERR_CONNECTION_TIMED_OUT` on `storage.<domain>` usually means Caddy route missing or DNS mismatch.
- `404` on `/` is expected; use `/api/health` and `/api/volumes`.
- If deploy logs mention GHCR `denied` or `not found`, verify `STORAGE_MANAGER_IMAGE` exists and GHCR credentials can pull it.
