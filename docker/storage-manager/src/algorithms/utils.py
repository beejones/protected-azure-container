from pathlib import Path


VALID_SORT_BY_VALUES = {"mtime", "ctime", "size"}


def iter_files(target_path: str) -> list[Path]:
    root = Path(target_path)
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return [item for item in root.rglob("*") if item.is_file()]


def validate_sort_by(sort_by: str) -> str:
    normalized = str(sort_by or "mtime").lower().strip()
    if normalized not in VALID_SORT_BY_VALUES:
        raise ValueError(f"Invalid sort_by '{sort_by}'. Allowed values: {sorted(VALID_SORT_BY_VALUES)}")
    return normalized
