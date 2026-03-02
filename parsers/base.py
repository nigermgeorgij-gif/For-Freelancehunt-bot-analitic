from abc import ABC, abstractmethod
from db.models import Project


class BaseParser(ABC):
    @abstractmethod
    async def fetch_projects(self) -> list[Project]:
        """Fetch new projects from the source."""

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
