from .base import CleanupAlgorithm, CleanupResult
from .utils import iter_files, validate_sort_by


class KeepNLatestAlgorithm(CleanupAlgorithm):
    def should_clean(self, target_path: str, params: dict) -> bool:
        keep_count = int(params.get("keep_count") or 0)
        if keep_count < 0:
            raise ValueError("keep_count must be >= 0")
        validate_sort_by(str(params.get("sort_by") or "mtime"))
        return len(iter_files(target_path)) > keep_count

    def clean(self, target_path: str, params: dict) -> CleanupResult:
        keep_count = int(params.get("keep_count") or 0)
        if keep_count < 0:
            raise ValueError("keep_count must be >= 0")

        sort_by = validate_sort_by(str(params.get("sort_by") or "mtime"))
        files = iter_files(target_path)
        if not files:
            return CleanupResult(cleaned=False, files_removed=0, bytes_freed=0)

        if sort_by == "ctime":
            files.sort(key=lambda item: float(item.stat().st_ctime), reverse=True)
        elif sort_by == "size":
            files.sort(key=lambda item: int(item.stat().st_size), reverse=True)
        else:
            files.sort(key=lambda item: float(item.stat().st_mtime), reverse=True)

        to_delete = files[keep_count:]
        removed_count = 0
        freed = 0

        for file_path in to_delete:
            file_size = int(file_path.stat().st_size)
            file_path.unlink(missing_ok=True)
            removed_count += 1
            freed += file_size

        return CleanupResult(cleaned=removed_count > 0, files_removed=removed_count, bytes_freed=freed)
