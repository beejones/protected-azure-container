from __future__ import annotations

import re
from typing import Any

from .models import upsert_registration


_STORAGE_MANAGER_LABEL_PATTERN = re.compile(r"^storage-manager\.(\d+)\.(.+)$")


def discover_registrations_from_container_labels(labels: dict[str, str] | None) -> list[dict[str, Any]]:
    if not labels:
        return []

    buckets: dict[int, dict[str, str]] = {}
    for key, value in labels.items():
        match = _STORAGE_MANAGER_LABEL_PATTERN.match(str(key))
        if not match:
            continue

        index = int(match.group(1))
        field_name = str(match.group(2))
        if index not in buckets:
            buckets[index] = {}
        buckets[index][field_name] = str(value)

    out: list[dict[str, Any]] = []
    for index in sorted(buckets.keys()):
        item = buckets[index]
        if not item.get("volume") or not item.get("path") or not item.get("algorithm"):
            continue

        params = {
            key: value
            for key, value in item.items()
            if key not in {"volume", "path", "algorithm", "description"}
        }

        payload: dict[str, Any] = {
            "volume_name": item["volume"],
            "path": item["path"],
            "algorithm": item["algorithm"],
            "params": params,
        }
        if item.get("description"):
            payload["description"] = item["description"]
        out.append(payload)

    return out


def discover_registrations_from_containers() -> list[dict[str, Any]]:
    import docker

    out: list[dict[str, Any]] = []
    client = docker.from_env()
    for container in client.containers.list():
        attrs = dict(container.attrs or {})
        config = dict(attrs.get("Config") or {})
        labels = config.get("Labels")
        registrations = discover_registrations_from_container_labels(labels)
        for item in registrations:
            out.append(item)
    return out


def sync_discovered_registrations(*, db_path: str, registrations: list[dict[str, Any]]) -> int:
    applied = 0
    for item in registrations:
        upsert_registration(
            db_path=db_path,
            volume_name=str(item["volume_name"]),
            path=str(item["path"]),
            algorithm=str(item["algorithm"]),
            params=dict(item.get("params") or {}),
            description=str(item["description"]) if item.get("description") is not None else None,
        )
        applied += 1
    return applied
