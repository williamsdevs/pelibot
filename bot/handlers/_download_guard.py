"""Shared download guard — checks subscription limit before downloading."""
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from services import subscription
from bot.handlers.payment import limit_reached_keyboard


async def check_and_record(update: Update, user_id: int) -> bool:
    """
    Check if user can download. If not, send limit message and return False.
    If yes, record the download and return True.
    """
    if subscription.can_download(user_id):
        subscription.record_download(user_id)
        return True

    msg = (
        f"🚫 *Límite alcanzado*\n\n"
        f"Has usado tus *{config.FREE_DOWNLOADS_PER_MONTH} descargas gratuitas* de este mes.\n\n"
        f"Actualiza a *Premium* por {config.PREMIUM_PRICE_STARS} ⭐ Stars/mes "
        f"y descarga sin límites."
    )

    # Works for both Message and CallbackQuery contexts
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=limit_reached_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=limit_reached_keyboard(),
        )
    return False
