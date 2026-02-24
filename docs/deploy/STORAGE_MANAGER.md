# Storage Manager

The Storage Manager is a lightweight service that monitors Docker volume paths and applies cleanup rules automatically.

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

## Compose label format

Use indexed labels to register one or more targets on a service:

```yaml
services:
  app:
    labels:
      storage-manager.0.volume: "protected-container_logs"
      storage-manager.0.path: "/"
      storage-manager.0.algorithm: "remove_before_date"
      storage-manager.0.max_age_days: "2"
      storage-manager.0.description: "Rotate code-server logs, keep last 2 days"
```

## Environment variables

Runtime (`env.example`):

- `SM_CHECK_INTERVAL_SECONDS=300`
- `SM_LOG_LEVEL=INFO`
- `SM_DB_PATH=/data/storage_manager.db`
- `SM_API_PORT=9100`

Deploy-time (`env.deploy.example`):

- `STORAGE_MANAGER_API_URL=https://storage.your-domain.com`

## Run locally

```bash
docker compose -f docker/storage-manager/docker-compose.yml up --build
```

The API will listen on container port `9100` and can be routed via centralized Caddy.
