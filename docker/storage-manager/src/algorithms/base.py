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
        """Return True when the target path should be cleaned."""

    @abstractmethod
    def clean(self, target_path: str, params: dict) -> CleanupResult:
        """Run cleanup and return details about removed files and bytes."""
