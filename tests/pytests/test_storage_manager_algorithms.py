from __future__ import annotations

import os
import sys
import time
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
STORAGE_MANAGER_SRC = REPO_ROOT / "docker" / "storage-manager" / "src"
if str(STORAGE_MANAGER_SRC) not in sys.path:
    sys.path.append(str(STORAGE_MANAGER_SRC))

_max_size_module = importlib.import_module("algorithms.max_size")
_remove_before_date_module = importlib.import_module("algorithms.remove_before_date")
_keep_n_latest_module = importlib.import_module("algorithms.keep_n_latest")

MaxSizeAlgorithm = _max_size_module.MaxSizeAlgorithm
RemoveBeforeDateAlgorithm = _remove_before_date_module.RemoveBeforeDateAlgorithm
KeepNLatestAlgorithm = _keep_n_latest_module.KeepNLatestAlgorithm


def _write_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_max_size_algorithm_removes_oldest_until_under_limit(tmp_path: Path) -> None:
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    third = tmp_path / "third.log"

    _write_file(first, 100)
    time.sleep(0.01)
    _write_file(second, 100)
    time.sleep(0.01)
    _write_file(third, 100)

    algo = MaxSizeAlgorithm()
    assert algo.should_clean(str(tmp_path), {"max_bytes": 250, "sort_by": "mtime"}) is True

    result = algo.clean(str(tmp_path), {"max_bytes": 250, "sort_by": "mtime"})
    assert result.cleaned is True
    assert result.files_removed == 1
    assert first.exists() is False
    assert second.exists() is True
    assert third.exists() is True


def test_remove_before_date_algorithm_removes_old_files(tmp_path: Path) -> None:
    old_file = tmp_path / "old.log"
    new_file = tmp_path / "new.log"

    _write_file(old_file, 10)
    _write_file(new_file, 10)

    old_timestamp = time.time() - (60 * 60 * 24 * 5)
    os.utime(old_file, (old_timestamp, old_timestamp))

    algo = RemoveBeforeDateAlgorithm()
    assert algo.should_clean(str(tmp_path), {"max_age_days": 2}) is True

    result = algo.clean(str(tmp_path), {"max_age_days": 2})
    assert result.cleaned is True
    assert result.files_removed == 1
    assert old_file.exists() is False
    assert new_file.exists() is True


def test_keep_n_latest_algorithm_keeps_n_newest(tmp_path: Path) -> None:
    first = tmp_path / "a.log"
    second = tmp_path / "b.log"
    third = tmp_path / "c.log"

    _write_file(first, 10)
    time.sleep(0.01)
    _write_file(second, 10)
    time.sleep(0.01)
    _write_file(third, 10)

    algo = KeepNLatestAlgorithm()
    assert algo.should_clean(str(tmp_path), {"keep_count": 2, "sort_by": "mtime"}) is True

    result = algo.clean(str(tmp_path), {"keep_count": 2, "sort_by": "mtime"})
    assert result.cleaned is True
    assert result.files_removed == 1
    assert first.exists() is False
    assert second.exists() is True
    assert third.exists() is True


def test_max_size_should_clean_raises_for_non_positive_max_bytes(tmp_path: Path) -> None:
    target = tmp_path / "f.log"
    _write_file(target, 10)

    algo = MaxSizeAlgorithm()
    try:
        algo.should_clean(str(tmp_path), {"max_bytes": 0, "sort_by": "mtime"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "max_bytes must be greater than 0" in str(exc)


def test_algorithms_raise_for_invalid_sort_by(tmp_path: Path) -> None:
    target = tmp_path / "f.log"
    _write_file(target, 10)

    max_size_algo = MaxSizeAlgorithm()
    keep_n_algo = KeepNLatestAlgorithm()

    try:
        max_size_algo.clean(str(tmp_path), {"max_bytes": 5, "sort_by": "unknown"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Invalid sort_by" in str(exc)


def test_keep_n_latest_keep_count_zero_deletes_all_files(tmp_path: Path) -> None:
    first = tmp_path / "a.log"
    second = tmp_path / "b.log"
    _write_file(first, 10)
    _write_file(second, 10)

    algo = KeepNLatestAlgorithm()
    assert algo.should_clean(str(tmp_path), {"keep_count": 0, "sort_by": "mtime"}) is True

    result = algo.clean(str(tmp_path), {"keep_count": 0, "sort_by": "mtime"})
    assert result.cleaned is True
    assert result.files_removed == 2
    assert first.exists() is False
    assert second.exists() is False


def test_algorithms_empty_directory_noop(tmp_path: Path) -> None:
    max_size_algo = MaxSizeAlgorithm()
    remove_before_algo = RemoveBeforeDateAlgorithm()
    keep_n_algo = KeepNLatestAlgorithm()

    assert max_size_algo.should_clean(str(tmp_path), {"max_bytes": 1, "sort_by": "mtime"}) is False
    assert remove_before_algo.should_clean(str(tmp_path), {"max_age_days": 2}) is False
    assert keep_n_algo.should_clean(str(tmp_path), {"keep_count": 1, "sort_by": "mtime"}) is False

    max_size_result = max_size_algo.clean(str(tmp_path), {"max_bytes": 1, "sort_by": "mtime"})
    remove_before_result = remove_before_algo.clean(str(tmp_path), {"max_age_days": 2})
    keep_n_result = keep_n_algo.clean(str(tmp_path), {"keep_count": 1, "sort_by": "mtime"})

    assert max_size_result.cleaned is False
    assert max_size_result.files_removed == 0
    assert remove_before_result.cleaned is False
    assert remove_before_result.files_removed == 0
    assert keep_n_result.cleaned is False
    assert keep_n_result.files_removed == 0


def test_max_size_exactly_at_limit_does_not_clean(tmp_path: Path) -> None:
    first = tmp_path / "a.log"
    second = tmp_path / "b.log"
    _write_file(first, 100)
    _write_file(second, 100)

    algo = MaxSizeAlgorithm()
    assert algo.should_clean(str(tmp_path), {"max_bytes": 200, "sort_by": "mtime"}) is False

    result = algo.clean(str(tmp_path), {"max_bytes": 200, "sort_by": "mtime"})
    assert result.cleaned is False
    assert result.files_removed == 0
    assert first.exists() is True
    assert second.exists() is True
