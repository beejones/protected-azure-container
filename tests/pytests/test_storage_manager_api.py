from __future__ import annotations

import importlib
import sys
from pathlib import Path
from urllib.parse import quote

from flask import Flask


REPO_ROOT = Path(__file__).parents[2]
STORAGE_MANAGER_ROOT = REPO_ROOT / "docker" / "storage-manager"
if str(STORAGE_MANAGER_ROOT) not in sys.path:
    sys.path.append(str(STORAGE_MANAGER_ROOT))


api = importlib.import_module("src.api")
models = importlib.import_module("src.models")


class DummyScheduler:
    def __init__(self, running: bool = True):
        self.is_running = running


def _build_test_client(*, db_path: str, scheduler_running: bool = True):
    app = Flask(__name__)
    app.register_blueprint(
        api.create_api_blueprint(db_path=db_path, scheduler=DummyScheduler(running=scheduler_running)),
        url_prefix="/api",
    )
    return app.test_client()


def test_register_and_unregister_flow(tmp_path: Path) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)
    client = _build_test_client(db_path=db_path)

    response = client.post(
        "/api/register",
        json={
            "volume_name": "protected-container_logs",
            "path": "/",
            "algorithm": "remove_before_date",
            "params": {"max_age_days": 14},
            "description": "keep recent logs",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["status"] == "ok"

    rows = models.list_registrations(db_path)
    assert len(rows) == 1
    assert rows[0]["volume_name"] == "protected-container_logs"

    encoded_path = quote(quote("/", safe=""), safe="")
    delete_response = client.delete(f"/api/register/protected-container_logs/{encoded_path}")
    assert delete_response.status_code == 200

    rows_after = models.list_registrations(db_path)
    assert rows_after == []


def test_register_returns_400_for_invalid_payload(tmp_path: Path) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)
    client = _build_test_client(db_path=db_path)

    response = client.post(
        "/api/register",
        json={
            "path": "/",
            "algorithm": "remove_before_date",
            "params": {},
        },
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert "volume_name is required" in payload["error"]


def test_health_reports_scheduler_state(tmp_path: Path) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)
    client = _build_test_client(db_path=db_path, scheduler_running=False)

    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["scheduler_running"] is False


def test_volumes_merges_docker_and_registered_entries(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)

    models.upsert_registration(
        db_path=db_path,
        volume_name="protected-container_logs",
        path="/",
        algorithm="remove_before_date",
        params={"max_age_days": 14},
        description="keep logs",
    )

    monkeypatch.setattr(
        api,
        "_list_docker_volumes",
        lambda: {
            "protected-container_logs": {
                "volume_name": "protected-container_logs",
                "driver": "local",
                "created_at": "2026-01-01T00:00:00Z",
                "mountpoint": "/var/lib/docker/volumes/protected-container_logs/_data",
                "containers": ["protected-container"],
            },
            "orphan-volume": {
                "volume_name": "orphan-volume",
                "driver": "local",
                "created_at": "2026-01-02T00:00:00Z",
                "mountpoint": "/var/lib/docker/volumes/orphan-volume/_data",
                "containers": [],
            },
        },
    )

    client = _build_test_client(db_path=db_path)
    response = client.get("/api/volumes")
    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload) == 2

    registered = next(item for item in payload if item["volume_name"] == "protected-container_logs")
    assert len(registered["registrations"]) == 1
    assert registered["registrations"][0]["algorithm"] == "remove_before_date"

    orphan = next(item for item in payload if item["volume_name"] == "orphan-volume")
    assert orphan["registrations"] == []


def test_volumes_query_name_filter(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)

    monkeypatch.setattr(
        api,
        "_list_docker_volumes",
        lambda: {
            "protected-container_logs": {
                "volume_name": "protected-container_logs",
                "driver": "local",
                "created_at": "2026-01-01T00:00:00Z",
                "mountpoint": None,
                "containers": [],
            },
            "camera-footage": {
                "volume_name": "camera-footage",
                "driver": "local",
                "created_at": "2026-01-02T00:00:00Z",
                "mountpoint": None,
                "containers": [],
            },
        },
    )

    client = _build_test_client(db_path=db_path)
    response = client.get("/api/volumes?name=logs")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 1
    assert payload[0]["volume_name"] == "protected-container_logs"


def test_volumes_query_registered_filter(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)

    models.upsert_registration(
        db_path=db_path,
        volume_name="protected-container_logs",
        path="/",
        algorithm="remove_before_date",
        params={"max_age_days": 14},
        description="keep logs",
    )

    monkeypatch.setattr(
        api,
        "_list_docker_volumes",
        lambda: {
            "protected-container_logs": {
                "volume_name": "protected-container_logs",
                "driver": "local",
                "created_at": "2026-01-01T00:00:00Z",
                "mountpoint": None,
                "containers": [],
            },
            "orphan-volume": {
                "volume_name": "orphan-volume",
                "driver": "local",
                "created_at": "2026-01-02T00:00:00Z",
                "mountpoint": None,
                "containers": [],
            },
        },
    )

    client = _build_test_client(db_path=db_path)

    response_registered = client.get("/api/volumes?registered=true")
    assert response_registered.status_code == 200
    payload_registered = response_registered.get_json()
    assert len(payload_registered) == 1
    assert payload_registered[0]["volume_name"] == "protected-container_logs"

    response_unregistered = client.get("/api/volumes?registered=false")
    assert response_unregistered.status_code == 200
    payload_unregistered = response_unregistered.get_json()
    assert len(payload_unregistered) == 1
    assert payload_unregistered[0]["volume_name"] == "orphan-volume"


def test_volumes_query_sort_current_bytes_and_created_at(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)

    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    v1.mkdir(parents=True, exist_ok=True)
    v2.mkdir(parents=True, exist_ok=True)
    (v1 / "a.bin").write_bytes(b"x" * 10)
    (v2 / "b.bin").write_bytes(b"y" * 100)

    monkeypatch.setattr(
        api,
        "_list_docker_volumes",
        lambda: {
            "small-volume": {
                "volume_name": "small-volume",
                "driver": "local",
                "created_at": "2026-01-01T00:00:00Z",
                "mountpoint": str(v1),
                "containers": [],
            },
            "big-volume": {
                "volume_name": "big-volume",
                "driver": "local",
                "created_at": "2026-01-02T00:00:00Z",
                "mountpoint": str(v2),
                "containers": [],
            },
        },
    )

    client = _build_test_client(db_path=db_path)

    response_bytes = client.get("/api/volumes?sort=current_bytes")
    assert response_bytes.status_code == 200
    payload_bytes = response_bytes.get_json()
    assert payload_bytes[0]["volume_name"] == "big-volume"
    assert int(payload_bytes[0]["current_bytes"]) >= int(payload_bytes[1]["current_bytes"])

    response_created = client.get("/api/volumes?sort=created_at")
    assert response_created.status_code == 200
    payload_created = response_created.get_json()
    assert payload_created[0]["volume_name"] == "big-volume"
