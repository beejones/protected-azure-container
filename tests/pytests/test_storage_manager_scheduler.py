from __future__ import annotations

import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
STORAGE_MANAGER_ROOT = REPO_ROOT / "docker" / "storage-manager"
if str(STORAGE_MANAGER_ROOT) not in sys.path:
    sys.path.append(str(STORAGE_MANAGER_ROOT))

scheduler_module = importlib.import_module("src.scheduler")
base_module = importlib.import_module("src.algorithms.base")


class _GoodAlgorithm:
    def should_clean(self, target_path: str, params: dict) -> bool:
        return True

    def clean(self, target_path: str, params: dict):
        return base_module.CleanupResult(cleaned=True, files_removed=3, bytes_freed=100)


class _BrokenAlgorithm:
    def should_clean(self, target_path: str, params: dict) -> bool:
        raise RuntimeError("boom")

    def clean(self, target_path: str, params: dict):
        raise RuntimeError("should not be called")


class _TestScheduler(scheduler_module.StorageScheduler):
    def _resolve_target_path(self, *, volume_name: str, relative_path: str) -> str | None:
        return "/tmp"


def test_scheduler_run_once_continues_after_registration_error(monkeypatch):
    monkeypatch.setattr(
        scheduler_module,
        "list_registrations",
        lambda db_path: [
            {
                "volume_name": "broken-volume",
                "path": "/",
                "algorithm": "broken",
                "params": {},
            },
            {
                "volume_name": "good-volume",
                "path": "/",
                "algorithm": "good",
                "params": {},
            },
        ],
    )

    calls: list[tuple[str, str, int]] = []

    def _capture_mark_cleanup_result(*, db_path: str, volume_name: str, path: str, files_removed: int):
        calls.append((volume_name, path, files_removed))

    monkeypatch.setattr(scheduler_module, "mark_cleanup_result", _capture_mark_cleanup_result)
    monkeypatch.setattr(
        scheduler_module,
        "ALGORITHM_REGISTRY",
        {
            "broken": _BrokenAlgorithm(),
            "good": _GoodAlgorithm(),
        },
    )

    scheduler = _TestScheduler(db_path="/tmp/storage_manager_test.db", check_interval_seconds=999)
    scheduler.run_once()

    assert len(calls) == 1
    assert calls[0] == ("good-volume", "/", 3)
