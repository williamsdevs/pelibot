"""Authorization middleware."""
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

import config


def restricted(func):
    """Decorator that blocks users not in ALLOWED_USER_IDS (if the list is configured)."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
            await update.effective_message.reply_text("⛔ No tienes permiso para usar este bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
