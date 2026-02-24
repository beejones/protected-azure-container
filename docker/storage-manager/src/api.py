from __future__ import annotations

from urllib.parse import unquote
from pathlib import Path

import docker
from flask import Blueprint, jsonify, request

from .models import delete_registration, list_registrations_by_volume, upsert_registration
from .scheduler import StorageScheduler


def _parse_registration_payload(payload: dict) -> dict:
    volume_name = str(payload.get("volume_name") or "").strip()
    path = str(payload.get("path") or "").strip()
    algorithm = str(payload.get("algorithm") or "").strip()
    params = payload.get("params") or {}
    description = payload.get("description")

    if not volume_name:
        raise ValueError("volume_name is required")
    if not path:
        raise ValueError("path is required")
    if not algorithm:
        raise ValueError("algorithm is required")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    return {
        "volume_name": volume_name,
        "path": path,
        "algorithm": algorithm,
        "params": params,
        "description": str(description) if description is not None else None,
    }


def _list_docker_volumes() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        client = docker.from_env()
        for volume in client.volumes.list():
            attrs = dict(volume.attrs or {})
            out[str(volume.name)] = {
                "volume_name": str(volume.name),
                "driver": str(attrs.get("Driver") or "local"),
                "created_at": attrs.get("CreatedAt"),
                "mountpoint": attrs.get("Mountpoint"),
                "containers": [],
            }
    except Exception:
        return {}
    return out


def _safe_volume_size_bytes(volume: dict) -> int:
    mountpoint = str(volume.get("mountpoint") or "")
    if not mountpoint:
        return 0
    root = Path(mountpoint)
    try:
        if not root.exists():
            return 0
        if root.is_file():
            return int(root.stat().st_size)

        total = 0
        for item in root.rglob("*"):
            if item.is_file():
                total += int(item.stat().st_size)
        return total
    except (PermissionError, OSError):
        return 0


def _apply_volumes_filters_and_sort(*, volumes: list[dict]) -> list[dict]:
    name_filter = str(request.args.get("name") or "").strip().lower()
    registered_filter = str(request.args.get("registered") or "").strip().lower()
    sort_key = str(request.args.get("sort") or "volume_name").strip().lower()

    out = list(volumes)

    if name_filter:
        out = [
            item
            for item in out
            if name_filter in str(item.get("volume_name") or "").lower()
        ]

    if registered_filter == "true":
        out = [item for item in out if bool(item.get("registrations"))]
    elif registered_filter == "false":
        out = [item for item in out if not bool(item.get("registrations"))]

    for item in out:
        item["current_bytes"] = _safe_volume_size_bytes(item)

    if sort_key == "current_bytes":
        out.sort(key=lambda item: int(item.get("current_bytes") or 0), reverse=True)
    elif sort_key == "created_at":
        out.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    else:
        out.sort(key=lambda item: str(item.get("volume_name") or ""))

    return out


def create_api_blueprint(*, db_path: str, scheduler: StorageScheduler) -> Blueprint:
    blueprint = Blueprint("storage_manager_api", __name__)

    @blueprint.post("/register")
    def register() -> tuple:
        payload = request.get_json(silent=True) or {}
        try:
            parsed = _parse_registration_payload(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        upsert_registration(
            db_path=db_path,
            volume_name=parsed["volume_name"],
            path=parsed["path"],
            algorithm=parsed["algorithm"],
            params=parsed["params"],
            description=parsed["description"],
        )

        return jsonify({"status": "ok", "registration": parsed}), 201

    @blueprint.delete("/register/<volume_name>/<path:encoded_path>")
    def unregister(volume_name: str, encoded_path: str) -> tuple:
        decoded_path = unquote(encoded_path)
        removed = delete_registration(db_path=db_path, volume_name=volume_name, path=decoded_path)
        if removed == 0:
            return jsonify({"error": "registration not found"}), 404
        return jsonify({"status": "ok"}), 200

    @blueprint.get("/volumes")
    def list_volumes() -> tuple:
        registrations_by_volume = list_registrations_by_volume(db_path)
        docker_volumes = _list_docker_volumes()

        for volume_name, registrations in registrations_by_volume.items():
            if volume_name not in docker_volumes:
                docker_volumes[volume_name] = {
                    "volume_name": volume_name,
                    "driver": "unknown",
                    "created_at": None,
                    "mountpoint": None,
                    "containers": [],
                }
            docker_volumes[volume_name]["registrations"] = registrations

        for item in docker_volumes.values():
            if "registrations" not in item:
                item["registrations"] = []

        values = _apply_volumes_filters_and_sort(volumes=list(docker_volumes.values()))
        return jsonify(values), 200

    @blueprint.get("/health")
    def health() -> tuple:
        return (
            jsonify(
                {
                    "status": "ok",
                    "scheduler_running": scheduler.is_running,
                }
            ),
            200,
        )

    return blueprint
