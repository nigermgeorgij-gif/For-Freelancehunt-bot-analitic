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

    parsers = []
    if settings.freelancehunt_api_token:
        parsers.append(FreelancehuntParser(settings.freelancehunt_api_token))
        logger.info("Freelancehunt parser enabled")
    else:
        logger.warning(
            "FREELANCEHUNT_API_TOKEN not set — Freelancehunt parser disabled"
        )

    monitoring: MonitoringService | None = None

    async def on_startup() -> None:
        nonlocal monitoring
        me = await bot.get_me()
        logger.info("Bot started: @%s", me.username)

        if parsers:
            # Use the bot owner's chat; in production, store admin chat_id in config
            monitoring = MonitoringService(
                bot=bot,
                chat_id=int(
                    # First message sender or fallback to bot id
                    me.id
                ),
                parsers=parsers,
                repository=repository,
                keywords=settings.keywords,
                polling_interval=settings.polling_interval,
            )
            asyncio.create_task(monitoring.start())

    async def on_shutdown() -> None:
        if monitoring:
            monitoring.stop()
        for parser in parsers:
            await parser.close()
        logger.info("Bot stopped")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
