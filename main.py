import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from config.settings import settings
from db.repository import ProjectRepository
from parsers.freelancehunt import FreelancehuntParser
from services.openai_service import OpenAIService
from services.monitoring import MonitoringService
from bot.handlers import router, setup as setup_handlers

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    repository = ProjectRepository(settings.database_path)
    await repository.init_db()

    openai_service = OpenAIService(
        api_key=settings.openai_api_key,
        system_prompt=settings.openai_system_prompt,
    )

    setup_handlers(repository, openai_service)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    parsers: list[FreelancehuntParser] = [FreelancehuntParser()]
    logger.info("Freelancehunt parser enabled")

    monitoring: MonitoringService | None = None
    monitoring_task: asyncio.Task | None = None

    async def on_startup() -> None:
        nonlocal monitoring, monitoring_task
        me = await bot.get_me()
        logger.info("Bot started: @%s", me.username)

        if not settings.telegram_admin_chat_id:
            logger.warning(
                "TELEGRAM_ADMIN_CHAT_ID not set — monitoring disabled. "
                "Send /start to the bot and set your chat ID in .env"
            )
            return

        if parsers:
            monitoring = MonitoringService(
                bot=bot,
                chat_id=settings.telegram_admin_chat_id,
                parsers=parsers,
                repository=repository,
                keywords=settings.keywords,
                polling_interval=settings.polling_interval,
            )
            monitoring_task = asyncio.create_task(monitoring.start())

    async def on_shutdown() -> None:
        if monitoring:
            monitoring.stop()
        if monitoring_task and not monitoring_task.done():
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
        for parser in parsers:
            await parser.close()
        await repository.close()
        logger.info("Bot stopped")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling…")
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Polling cancelled")


if __name__ == "__main__":
    asyncio.run(main())
