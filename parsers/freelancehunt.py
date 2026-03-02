import logging
import httpx
from parsers.base import BaseParser
from db.models import Project

logger = logging.getLogger(__name__)

FREELANCEHUNT_API_URL = "https://api.freelancehunt.com/v2/projects"


class FreelancehuntParser(BaseParser):
    def __init__(self, api_token: str) -> None:
        self._api_token = api_token
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
        )

    async def fetch_projects(self) -> list[Project]:
        try:
            response = await self._client.get(FREELANCEHUNT_API_URL)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except httpx.HTTPStatusError as e:
            logger.error(
                "Freelancehunt API HTTP error: %s %s",
                e.response.status_code,
                e.response.text[:200],
            )
            return []
        except httpx.RequestError as e:
            logger.error("Freelancehunt API request error: %s", e)
            return []
        except Exception as e:
            logger.exception("Unexpected error fetching projects: %s", e)
            return []

    def _parse_response(self, data: dict) -> list[Project]:
        projects: list[Project] = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            project = Project(
                external_id=str(item.get("id", "")),
                title=attrs.get("name", ""),
                description=attrs.get("description", "")[:1000],
                url=item.get("links", {}).get("self", {}).get("api", ""),
                budget=(
                    f"{attrs.get('budget', {}).get('amount', 'N/A')} "
                    f"{attrs.get('budget', {}).get('currency', '')}"
                ),
                source="freelancehunt",
            )
            projects.append(project)
        logger.info("Fetched %d projects from Freelancehunt", len(projects))
        return projects

    async def close(self) -> None:
        await self._client.aclose()
