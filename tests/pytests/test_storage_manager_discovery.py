from __future__ import annotations

import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
STORAGE_MANAGER_ROOT = REPO_ROOT / "docker" / "storage-manager"
if str(STORAGE_MANAGER_ROOT) not in sys.path:
    sys.path.append(str(STORAGE_MANAGER_ROOT))


discovery = importlib.import_module("src.discovery")
models = importlib.import_module("src.models")


def test_discover_registrations_from_container_labels_extracts_indexed_items() -> None:
    labels = {
        "storage-manager.0.volume": "protected-container_logs",
        "storage-manager.0.path": "/",
        "storage-manager.0.algorithm": "remove_before_date",
        "storage-manager.0.max_age_days": "14",
        "storage-manager.1.volume": "camera-footage",
        "storage-manager.1.path": "/recordings",
        "storage-manager.1.algorithm": "max_size",
        "storage-manager.1.max_bytes": "12345",
        "other.label": "ignored",
    }

    out = discovery.discover_registrations_from_container_labels(labels)
    assert len(out) == 2

    first = out[0]
    assert first["volume_name"] == "protected-container_logs"
    assert first["path"] == "/"
    assert first["algorithm"] == "remove_before_date"
    assert first["params"]["max_age_days"] == "14"

    second = out[1]
    assert second["volume_name"] == "camera-footage"
    assert second["algorithm"] == "max_size"
    assert second["params"]["max_bytes"] == "12345"


def test_sync_discovered_registrations_writes_to_sqlite(tmp_path: Path) -> None:
    db_path = str(tmp_path / "storage_manager.db")
    models.init_db(db_path)

    applied = discovery.sync_discovered_registrations(
        db_path=db_path,
        registrations=[
            {
                "volume_name": "protected-container_logs",
                "path": "/",
                "algorithm": "remove_before_date",
                "params": {"max_age_days": "14"},
                "description": "keep logs",
            }
        ],
    )

    assert applied == 1

    rows = models.list_registrations(db_path)
    assert len(rows) == 1
    assert rows[0]["volume_name"] == "protected-container_logs"
    assert rows[0]["algorithm"] == "remove_before_date"
    assert rows[0]["params"]["max_age_days"] == "14"
    assert rows[0]["description"] == "keep logs"
