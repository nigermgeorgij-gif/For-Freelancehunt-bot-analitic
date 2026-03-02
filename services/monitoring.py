import asyncio
import hashlib
import html
import logging
import re
import time
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
SCORE_KEYWORDS_ANY = {"бот": 1, "bot": 1, "automation": 1}
SCORE_BUDGET_THRESHOLD = 10000
SCORE_BUDGET_POINTS = 2


class MonitoringService:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        parsers: list[BaseParser],
        repository: ProjectRepository,
        blacklist: list[str],
        whitelist: list[str],
        polling_interval: int = 60,
        priority_threshold: int = 1,
        ignored_log_interval_hours: int = 6,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._parsers = parsers
        self._repository = repository
        self._blacklist = [w.lower() for w in blacklist]
        self._whitelist = [w.lower() for w in whitelist]
        self._polling_interval = max(polling_interval, MIN_POLLING_INTERVAL)
        self._priority_threshold = priority_threshold
        self._ignored_log_interval = ignored_log_interval_hours * 3600
        self._running = False
        self._lock = asyncio.Lock()
        self._last_ignored_at: dict[str, float] = {}

    def _is_blacklisted(self, project: Project) -> bool:
        text = f"{project.title} {project.description}".lower()
        return any(word in text for word in self._blacklist)

    def _matches_whitelist(self, project: Project) -> bool:
        text = f"{project.title} {project.description}".lower()
        return any(word in text for word in self._whitelist)

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
    def _format_label(status: str, score: int) -> str:
        priority = "HIGH" if score >= 3 else "MEDIUM"
        icon = "🔄" if status == "UPDATED" else "🆕"
        return f"{icon} [{status} | {priority}]"

    @staticmethod
    def _format_project(project: Project, label: str) -> str:
        desc = html.escape(project.description[:500])
        title = html.escape(project.title)
        budget = html.escape(project.budget)
        source = html.escape(project.source)
        url = html.escape(project.url)
        text = (
            f"{label}\n"
            f"<b>{title}</b>\n\n"
            f"{desc}\n\n"
            f"💰 Budget: {budget}\n"
            f"🔗 Source: {source}\n"
            f"🌐 {url}"
        )
        return text[:MAX_MESSAGE_LEN]

    def _log_ignored(self, external_id: str, reason: str) -> None:
        now = time.monotonic()
        key = f"{external_id}:{reason}"
        last_logged = self._last_ignored_at.get(key)
        if last_logged is None or now - last_logged > self._ignored_log_interval:
            logger.info("Project ignored (%s): %s", reason, external_id)
            self._last_ignored_at[key] = now

    async def _process_projects(self) -> None:
        stats = {
            "total_parsed": 0,
            "new_projects": 0,
            "updated_projects": 0,
            "ignored_blacklist": 0,
            "ignored_whitelist": 0,
            "ignored_low_score": 0,
            "skipped_no_changes": 0,
            "sent_to_telegram": 0,
        }

        for parser in self._parsers:
            try:
                projects = await parser.fetch_projects()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Parser error: %s", e)
                continue

            stats["total_parsed"] += len(projects)

            for project in projects:
                content_hash = self._compute_content_hash(project)
                existing_hash = await self._repository.get_content_hash(
                    project.external_id
                )

                if existing_hash is not None and existing_hash == content_hash:
                    stats["skipped_no_changes"] += 1
                    continue

                is_update = existing_hash is not None

                if self._is_blacklisted(project):
                    stats["ignored_blacklist"] += 1
                    self._log_ignored(project.external_id, "blacklisted")
                    continue

                if not self._matches_whitelist(project):
                    stats["ignored_whitelist"] += 1
                    self._log_ignored(project.external_id, "no whitelist match")
                    continue

                budget_value = self._extract_budget_value(project.budget)
                score = self._calculate_score(project, budget_value)

                if score < self._priority_threshold:
                    stats["ignored_low_score"] += 1
                    self._log_ignored(project.external_id, "low score")
                    continue

                now = datetime.now(timezone.utc).isoformat()
                project.content_hash = content_hash
                project.notified_at = now

                if is_update:
                    await self._repository.update_project(project)
                    stats["updated_projects"] += 1
                    logger.info("UPDATED project: %s", project.external_id)
                else:
                    await self._repository.save_project(project)
                    stats["new_projects"] += 1
                    logger.info("NEW project: %s", project.external_id)

                status = "UPDATED" if is_update else "NEW"
                label = self._format_label(status, score)

                try:
                    await self._bot.send_message(
                        chat_id=self._chat_id,
                        text=self._format_project(project, label),
                        parse_mode="HTML",
                        reply_markup=project_keyboard(project.external_id),
                    )
                    stats["sent_to_telegram"] += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Failed to send message: %s", e)

        logger.info(
            "Cycle summary: parsed=%d new=%d updated=%d sent=%d "
            "ignored_bl=%d ignored_wl=%d ignored_score=%d skipped=%d",
            stats["total_parsed"],
            stats["new_projects"],
            stats["updated_projects"],
            stats["sent_to_telegram"],
            stats["ignored_blacklist"],
            stats["ignored_whitelist"],
            stats["ignored_low_score"],
            stats["skipped_no_changes"],
        )

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
