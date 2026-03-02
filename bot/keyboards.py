from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def project_keyboard(project_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Generate Proposal",
                    callback_data=f"proposal:{project_id}",
                )
            ]
        ]
    )
