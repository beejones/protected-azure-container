from .base import CleanupAlgorithm, CleanupResult
from .utils import iter_files, validate_sort_by


def _total_size(files: list) -> int:
    return sum(int(item.stat().st_size) for item in files if item.exists())


class MaxSizeAlgorithm(CleanupAlgorithm):
    def should_clean(self, target_path: str, params: dict) -> bool:
        max_bytes = int(params.get("max_bytes") or 0)
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than 0")
        validate_sort_by(str(params.get("sort_by") or "mtime"))
        files = iter_files(target_path)
        return _total_size(files) > max_bytes

    def clean(self, target_path: str, params: dict) -> CleanupResult:
        max_bytes = int(params.get("max_bytes") or 0)
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than 0")

        sort_by = validate_sort_by(str(params.get("sort_by") or "mtime"))
        files = iter_files(target_path)
        if not files:
            return CleanupResult(cleaned=False, files_removed=0, bytes_freed=0)

        if sort_by == "size":
            files.sort(key=lambda item: int(item.stat().st_size), reverse=True)
        elif sort_by == "ctime":
            files.sort(key=lambda item: float(item.stat().st_ctime))
        else:
            files.sort(key=lambda item: float(item.stat().st_mtime))

        current_size = _total_size(files)
        removed_count = 0
        freed = 0

        for file_path in files:
            if current_size <= max_bytes:
                break
            file_size = int(file_path.stat().st_size)
            file_path.unlink(missing_ok=True)
            current_size -= file_size
            removed_count += 1
            freed += file_size

        return CleanupResult(cleaned=removed_count > 0, files_removed=removed_count, bytes_freed=freed)
