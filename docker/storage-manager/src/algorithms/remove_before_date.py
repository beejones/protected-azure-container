from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import CleanupAlgorithm, CleanupResult


def _iter_files(target_path: str) -> list[Path]:
    root = Path(target_path)
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return [item for item in root.rglob("*") if item.is_file()]


def _parse_threshold(params: dict) -> datetime:
    before_date = params.get("before_date")
    max_age_days = params.get("max_age_days")

    if before_date:
        parsed = datetime.fromisoformat(str(before_date).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    if max_age_days is not None:
        days = int(max_age_days)
        return datetime.now(timezone.utc) - timedelta(days=days)

    raise ValueError("Either before_date or max_age_days must be provided")


class RemoveBeforeDateAlgorithm(CleanupAlgorithm):
    def should_clean(self, target_path: str, params: dict) -> bool:
        threshold = _parse_threshold(params)
        for file_path in _iter_files(target_path):
            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if modified < threshold:
                return True
        return False

    def clean(self, target_path: str, params: dict) -> CleanupResult:
        threshold = _parse_threshold(params)
        removed_count = 0
        freed = 0

        for file_path in _iter_files(target_path):
            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if modified < threshold:
                file_size = int(file_path.stat().st_size)
                file_path.unlink(missing_ok=True)
                removed_count += 1
                freed += file_size

        return CleanupResult(cleaned=removed_count > 0, files_removed=removed_count, bytes_freed=freed)
