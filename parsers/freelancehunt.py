import asyncio
import logging

import httpx
from selectolax.parser import HTMLParser

from db.models import Project
from parsers.base import BaseParser

logger = logging.getLogger(__name__)

MAX_PROJECTS = 50
MAX_RETRIES = 3
FREELANCEHUNT_URL = "https://freelancehunt.com/projects"


class FreelancehuntParser(BaseParser):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def fetch_projects(self) -> list[Project]:
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.get(FREELANCEHUNT_URL)
                response.raise_for_status()
                return self._parse_html(response.text)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = 2 ** (attempt + 1)
                    logger.warning(
                        "Freelancehunt fetch error (attempt %d/%d): %s — retrying in %ds",
                        attempt + 1, MAX_RETRIES, e, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Freelancehunt fetch failed after %d attempts: %s",
                        MAX_RETRIES, e,
                    )
        return []

    @staticmethod
    def _parse_html(html: str) -> list[Project]:
        tree = HTMLParser(html)
        projects: list[Project] = []
        seen_ids: set[str] = set()

        for link_node in tree.css('a[href*="/project/"]'):
            if len(projects) >= MAX_PROJECTS:
                break
            try:
                href = link_node.attributes.get("href", "")
                if not href.endswith(".html"):
                    continue

                parts = href.rstrip("/").split("/")
                external_id = ""
                for part in reversed(parts):
                    clean = part.replace(".html", "")
                    if clean.isdigit():
                        external_id = clean
                        break
                if not external_id or external_id in seen_ids:
                    continue

                title = link_node.text(strip=True)
                if not title:
                    continue
                seen_ids.add(external_id)

                url = href if href.startswith("http") else f"https://freelancehunt.com{href}"

                projects.append(Project(
                    external_id=external_id,
                    title=title,
                    description="",
                    url=url,
                    budget="N/A",
                    source="freelancehunt",
                ))
            except Exception as e:
                logger.error("Error parsing project link: %s", e)
                continue

        logger.info("Parsed %d projects from Freelancehunt", len(projects))
        return projects

    async def close(self) -> None:
        await self._client.aclose()
