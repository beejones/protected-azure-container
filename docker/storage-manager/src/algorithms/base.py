from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CleanupResult:
    cleaned: bool
    files_removed: int
    bytes_freed: int


class CleanupAlgorithm(ABC):
    @abstractmethod
    def should_clean(self, target_path: str, params: dict) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clean(self, target_path: str, params: dict) -> CleanupResult:
        raise NotImplementedError
