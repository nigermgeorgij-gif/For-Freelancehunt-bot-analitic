import asyncio
import hashlib
import html
import logging
import re
from datetime import datetime, timezone

from aiogram import Bot
from db.models import Project
from db.repository import ProjectRepository
from parsers.base import BaseParser
from bot.keyboards import project_keyboard

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4000
MIN_POLLING_INTERVAL = 60

SCORE_KEYWORDS_TITLE = {"ai": 2}
SCORE_KEYWORDS_DESCRIPTION = {"python": 1}
SCORE_KEYWORDS_ANY = {"бот": 1, "automation": 1}
SCORE_BUDGET_THRESHOLD = 10000
SCORE_BUDGET_POINTS = 2


class MonitoringService:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        parsers: list[BaseParser],
        repository: ProjectRepository,
        keywords: list[str],
        polling_interval: int = 60,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._parsers = parsers
        self._repository = repository
        self._keywords = [kw.lower() for kw in keywords]
        self._polling_interval = max(polling_interval, MIN_POLLING_INTERVAL)
        self._running = False
        self._lock = asyncio.Lock()

    def _matches_keywords(self, project: Project) -> bool:
        text = f"{project.title} {project.description}".lower()
        return any(kw in text for kw in self._keywords)

    @staticmethod
    def _compute_content_hash(project: Project) -> str:
        payload = f"{project.title}|{project.description}|{project.budget}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_budget_value(budget: str) -> int:
        numbers = re.findall(r"\d+", budget.replace(" ", ""))
        if numbers:
            return int(numbers[0])
        return 0

    @staticmethod
    def _calculate_score(project: Project, budget_value: int) -> int:
        score = 0
        title_lower = project.title.lower()
        desc_lower = project.description.lower()
        combined = f"{title_lower} {desc_lower}"

        for kw, points in SCORE_KEYWORDS_TITLE.items():
            if kw in title_lower:
                score += points

        for kw, points in SCORE_KEYWORDS_DESCRIPTION.items():
            if kw in desc_lower:
                score += points

        for kw, points in SCORE_KEYWORDS_ANY.items():
            if kw in combined:
                score += points

        if budget_value > SCORE_BUDGET_THRESHOLD:
            score += SCORE_BUDGET_POINTS

        return score

    @staticmethod
    def _priority_label(score: int) -> str:
        if score >= 3:
            return "🔴 [HIGH PRIORITY]"
        return "🟡 [MEDIUM]"

    @staticmethod
    def _format_project(project: Project, label: str, is_update: bool = False) -> str:
        desc = html.escape(project.description[:500])
        title = html.escape(project.title)
        budget = html.escape(project.budget)
        source = html.escape(project.source)
        url = html.escape(project.url)
        prefix = "🔄 UPDATED" if is_update else "🆕"
        text = (
            f"{label}\n"
            f"{prefix} <b>{title}</b>\n\n"
            f"{desc}\n\n"
            f"💰 Budget: {budget}\n"
            f"🔗 Source: {source}\n"
            f"🌐 {url}"
        )
        return text[:MAX_MESSAGE_LEN]

    async def _process_projects(self) -> None:
        for parser in self._parsers:
            try:
                projects = await parser.fetch_projects()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Parser error: %s", e)
                continue

            for project in projects:
                if not self._matches_keywords(project):
                    continue

                content_hash = self._compute_content_hash(project)
                budget_value = self._extract_budget_value(project.budget)
                score = self._calculate_score(project, budget_value)

                if score == 0:
                    logger.debug(
                        "Project ignored (low score): %s", project.external_id
                    )
                    continue

                existing_hash = await self._repository.get_content_hash(
                    project.external_id
                )
                is_update = False

                if existing_hash is None:
                    project.content_hash = content_hash
                    project.notified_at = datetime.now(timezone.utc).isoformat()
                    await self._repository.save_project(project)
                    logger.info("NEW project detected: %s", project.external_id)
                elif existing_hash != content_hash:
                    project.content_hash = content_hash
                    project.notified_at = datetime.now(timezone.utc).isoformat()
                    await self._repository.update_project(project)
                    is_update = True
                    logger.info("UPDATED project detected: %s", project.external_id)
                else:
                    logger.debug(
                        "Project skipped (no changes): %s", project.external_id
                    )
                    continue

                label = self._priority_label(score)

                try:
                    await self._bot.send_message(
                        chat_id=self._chat_id,
                        text=self._format_project(project, label, is_update),
                        parse_mode="HTML",
                        reply_markup=project_keyboard(project.external_id),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Failed to send message: %s", e)

    async def start(self) -> None:
        self._running = True
        logger.info("Monitoring started (interval=%ds)", self._polling_interval)
        try:
            while self._running:
                async with self._lock:
                    await self._process_projects()
                await asyncio.sleep(self._polling_interval)
        except asyncio.CancelledError:
            logger.info("Monitoring task cancelled")

    def stop(self) -> None:
        self._running = False
        logger.info("Monitoring stopped")
