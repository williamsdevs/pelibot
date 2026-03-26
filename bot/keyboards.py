"""Inline keyboard builders."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.jackett import TorrentResult


def torrent_list_keyboard(results: list) -> InlineKeyboardMarkup:
    """Build inline keyboard where each button represents a torrent result."""
    buttons = []
    for i, r in enumerate(results):
        label = f"{i+1}. {r.title[:35]} | {r.size_gb} | {r.seeders}🌱"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl:{i}")])
    buttons.append([InlineKeyboardButton("🤖 Elección automática con IA", callback_data="ai_pick")])
    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Descargar", callback_data=f"confirm:{index}"),
            InlineKeyboardButton("🔙 Volver", callback_data="back"),
        ]
    ])
