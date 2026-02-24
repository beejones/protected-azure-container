from __future__ import annotations

import logging
import os

import docker
from apscheduler.schedulers.background import BackgroundScheduler

from .algorithms import ALGORITHM_REGISTRY
from .models import list_registrations, mark_cleanup_result


LOGGER = logging.getLogger("storage_manager")


class StorageScheduler:
    def __init__(self, *, db_path: str, check_interval_seconds: int = 300):
        self._db_path = db_path
        self._check_interval_seconds = int(check_interval_seconds)
        self._scheduler = BackgroundScheduler()
        self._running = False
        self._docker_client = None
        try:
            self._docker_client = docker.from_env()
        except Exception:
            LOGGER.warning("[STORAGE]: Docker client unavailable at scheduler init", exc_info=True)
        self._scheduler.add_job(self.run_once, "interval", seconds=self._check_interval_seconds)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._scheduler.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        self._scheduler.shutdown(wait=False)
        self._running = False

    def run_once(self) -> None:
        for registration in list_registrations(self._db_path):
            try:
                algorithm_name = str(registration.get("algorithm") or "")
                algorithm = ALGORITHM_REGISTRY.get(algorithm_name)
                if algorithm is None:
                    LOGGER.warning(
                        "[STORAGE]: Unknown algorithm '%s' for %s:%s",
                        algorithm_name,
                        registration.get("volume_name"),
                        registration.get("path"),
                    )
                    continue

                target_path = self._resolve_target_path(
                    volume_name=str(registration["volume_name"]),
                    relative_path=str(registration["path"]),
                )
                if not target_path:
                    continue

                params = dict(registration.get("params") or {})
                if algorithm.should_clean(target_path, params):
                    result = algorithm.clean(target_path, params)
                    mark_cleanup_result(
                        db_path=self._db_path,
                        volume_name=str(registration["volume_name"]),
                        path=str(registration["path"]),
                        files_removed=int(result.files_removed),
                    )
            except Exception:
                LOGGER.warning(
                    "[STORAGE]: Cleanup failed for %s:%s",
                    registration.get("volume_name"),
                    registration.get("path"),
                    exc_info=True,
                )

    def _resolve_target_path(self, *, volume_name: str, relative_path: str) -> str | None:
        try:
            if self._docker_client is None:
                return None
            volume = self._docker_client.volumes.get(volume_name)
            mountpoint = str(volume.attrs.get("Mountpoint") or "")
        except Exception:
            return None

        if not mountpoint:
            return None

        normalized = relative_path.lstrip("/")
        if not normalized:
            return mountpoint
        return os.path.join(mountpoint, normalized)
