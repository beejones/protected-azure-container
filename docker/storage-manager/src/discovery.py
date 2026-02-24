from __future__ import annotations

import re
from typing import Any


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
