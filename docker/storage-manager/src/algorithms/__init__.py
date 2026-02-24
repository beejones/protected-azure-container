from .base import CleanupAlgorithm, CleanupResult
from .keep_n_latest import KeepNLatestAlgorithm
from .max_size import MaxSizeAlgorithm
from .remove_before_date import RemoveBeforeDateAlgorithm


ALGORITHM_REGISTRY: dict[str, CleanupAlgorithm] = {
    "max_size": MaxSizeAlgorithm(),
    "remove_before_date": RemoveBeforeDateAlgorithm(),
    "keep_n_latest": KeepNLatestAlgorithm(),
}


__all__ = [
    "CleanupAlgorithm",
    "CleanupResult",
    "MaxSizeAlgorithm",
    "RemoveBeforeDateAlgorithm",
    "KeepNLatestAlgorithm",
    "ALGORITHM_REGISTRY",
]
