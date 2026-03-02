import asyncio
import logging
from aiogram import Bot
from db.models import Project
from db.repository import ProjectRepository
from parsers.base import BaseParser
from bot.keyboards import project_keyboard

logger = logging.getLogger(__name__)


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
        self._polling_interval = polling_interval
        self._running = False

    def _matches_keywords(self, project: Project) -> bool:
        text = f"{project.title} {project.description}".lower()
        return any(kw in text for kw in self._keywords)

    def _format_project(self, project: Project) -> str:
        return (
            f"🆕 <b>{project.title}</b>\n\n"
            f"{project.description[:500]}\n\n"
            f"💰 Budget: {project.budget}\n"
            f"🔗 Source: {project.source}\n"
            f"🌐 {project.url}"
        )

    async def _process_projects(self) -> None:
        for parser in self._parsers:
            try:
                projects = await parser.fetch_projects()
            except Exception as e:
                logger.error("Parser error: %s", e)
                continue

            for project in projects:
                if await self._repository.project_exists(project.external_id):
                    continue

                if not self._matches_keywords(project):
                    continue

                await self._repository.save_project(project)

                try:
                    await self._bot.send_message(
                        chat_id=self._chat_id,
                        text=self._format_project(project),
                        parse_mode="HTML",
                        reply_markup=project_keyboard(project.external_id),
                    )
                except Exception as e:
                    logger.error("Failed to send message: %s", e)

                await asyncio.sleep(0.5)

    async def start(self) -> None:
        self._running = True
        logger.info("Monitoring started (interval=%ds)", self._polling_interval)
        while self._running:
            await self._process_projects()
            await asyncio.sleep(self._polling_interval)

    def stop(self) -> None:
        self._running = False
        logger.info("Monitoring stopped")
