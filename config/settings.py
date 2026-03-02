import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

PROFILE_CONTEXT = """
Специализация: AI Product Engineer / Python интегратор

Основной стек:

Python (asyncio, aiogram, automation)

OpenAI API

Telegram bots

HTML parsing (selectolax)

REST API

CRM automation

Supabase

PDF generation

Опыт:

AI-воронки

CRM интеграции

Мониторинг-боты

Автоматизация бизнес-процессов

Подход:

Быстрая реализация

Чистая архитектура

Фокус на бизнес-результат
"""


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_admin_chat_id: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "projects.db")
    )
    polling_interval: int = field(
        default_factory=lambda: int(os.getenv("POLLING_INTERVAL", "60"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    keywords: list[str] = field(default_factory=lambda: [
        "python", "api", "shopify", "google merchant", "crm",
        "automation", "dashboard", "django", "fastapi", "flask",
        "telegram", "bot", "scraping", "parsing", "ai", "бот",
    ])

    openai_system_prompt: str = field(default_factory=lambda: (
        "Ты пишешь отклик на фриланс-проект.\n"
        f"Вот профиль специалиста:\n{PROFILE_CONTEXT}\n"
        "Напиши краткий, уверенный отклик.\n"
        "Не выдумывай опыт.\n"
        "Используй только стек из профиля.\n"
        "Без воды.\n"
        "До 1200 символов."
    ))


settings = Settings()
