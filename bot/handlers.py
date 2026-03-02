import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from db.repository import ProjectRepository
from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

router = Router()

_repository: ProjectRepository | None = None
_openai_service: OpenAIService | None = None


def setup(repository: ProjectRepository, openai_service: OpenAIService) -> None:
    global _repository, _openai_service
    _repository = repository
    _openai_service = openai_service


@router.message(F.text == "/start")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Freelance Monitor Bot\n\n"
        "I monitor freelance platforms and send matching projects.\n\n"
        f"Your chat ID: <code>{message.chat.id}</code>\n\n"
        "Commands:\n"
        "/start — Show this message\n"
        "/status — Bot status",
        parse_mode="HTML",
    )


@router.message(F.text == "/status")
async def cmd_status(message: Message) -> None:
    await message.answer("✅ Bot is running and monitoring projects.")


@router.callback_query(F.data.startswith("proposal:"))
async def on_generate_proposal(callback: CallbackQuery) -> None:
    if _repository is None or _openai_service is None:
        await callback.answer("Bot not fully initialized.", show_alert=True)
        return

    project_id = callback.data.split(":", 1)[1]
    project = await _repository.get_project(project_id)

    if project is None:
        await callback.answer("Project not found.", show_alert=True)
        return

    await callback.answer("Generating proposal…")

    proposal = await _openai_service.generate_proposal(
        project.title, project.description
    )

    await callback.message.answer(
        f"📝 <b>Proposal for:</b> {project.title}\n\n{proposal}",
        parse_mode="HTML",
    )
