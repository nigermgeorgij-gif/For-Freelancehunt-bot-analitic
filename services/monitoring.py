import asyncio
import html
import logging
from aiogram import Bot
from db.models import Project
from db.repository import ProjectRepository
from parsers.base import BaseParser
from bot.keyboards import project_keyboard

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4000
MIN_POLLING_INTERVAL = 60


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
    def _format_project(project: Project) -> str:
        desc = html.escape(project.description[:500])
        title = html.escape(project.title)
        budget = html.escape(project.budget)
        source = html.escape(project.source)
        url = html.escape(project.url)
        text = (
            f"🆕 <b>{title}</b>\n\n"
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
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Failed to send message: %s", e)

    async def start(self) -> None:
        self._running = True
        logger.info("Monitoring started (interval=%ds)", self._polling_interval)
        try:
            while self._running:
                if not self._lock.locked():
                    async with self._lock:
                        await self._process_projects()
                await asyncio.sleep(self._polling_interval)
        except asyncio.CancelledError:
            logger.info("Monitoring task cancelled")

    def stop(self) -> None:
        self._running = False
        logger.info("Monitoring stopped")
