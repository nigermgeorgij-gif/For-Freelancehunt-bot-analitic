import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


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
        "telegram", "bot", "scraping", "parsing",
    ])

    openai_system_prompt: str = field(default_factory=lambda: (
        "You are an experienced freelance developer. "
        "Write a concise, professional proposal for the given project. "
        "Highlight relevant skills and experience. "
        "Keep it under 150 words. Be specific to the project requirements."
    ))


settings = Settings()
