import asyncio
import logging
import httpx
from selectolax.parser import HTMLParser
from parsers.base import BaseParser
from db.models import Project

logger = logging.getLogger(__name__)

FREELANCEHUNT_URL = "https://freelancehunt.com/projects"
MAX_PROJECTS = 20
MAX_RETRIES = 3


class FreelancehuntParser(BaseParser):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html",
                "Accept-Language": "uk,en;q=0.9",
            },
        )

    async def fetch_projects(self) -> list[Project]:
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.get(FREELANCEHUNT_URL)
                response.raise_for_status()
                return self._parse_html(response.text)
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Freelancehunt HTTP error: %s", e.response.status_code,
                )
                return []
            except asyncio.CancelledError:
                raise
            except httpx.RequestError as e:
                delay = 2 ** (attempt + 1)
                logger.error(
                    "Freelancehunt request error (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                if attempt == MAX_RETRIES - 1:
                    return []
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error("Unexpected error fetching projects: %s", e)
                return []
        return []

    @staticmethod
    def _parse_html(html: str) -> list[Project]:
        tree = HTMLParser(html)
        projects: list[Project] = []

        for card in tree.css("div.project-card")[:MAX_PROJECTS]:
            try:
                link_node = card.css_first("a.project-card__title")
                if link_node is None:
                    continue
                href = link_node.attributes.get("href", "")
                title = link_node.text(strip=True)

                # extract numeric id from URL like /project/slug/1234567.html
                external_id = ""
                parts = href.rstrip("/").split("/")
                for part in reversed(parts):
                    clean = part.replace(".html", "")
                    if clean.isdigit():
                        external_id = clean
                        break
                if not external_id:
                    continue

                url = href if href.startswith("http") else f"https://freelancehunt.com{href}"

                desc_node = card.css_first("div.project-card__description")
                description = desc_node.text(strip=True)[:500] if desc_node else ""

                budget_node = card.css_first("div.project-card__budget")
                budget = budget_node.text(strip=True) if budget_node else "N/A"

                projects.append(Project(
                    external_id=external_id,
                    title=title,
                    description=description,
                    url=url,
                    budget=budget,
                    source="freelancehunt",
                ))
            except Exception as e:
                logger.error("Error parsing project card: %s", e)
                continue

        logger.info("Parsed %d projects from Freelancehunt", len(projects))
        return projects

    async def close(self) -> None:
        await self._client.aclose()
