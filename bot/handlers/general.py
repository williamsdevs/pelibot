"""General command handlers: /start, /help."""
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import storage

_seen_users: set[int] = set()

HELP_TEXT = """
🤖 *PeliBot* — Tu gestor de descargas de Telegram

🎬 *Películas (YTS):*
• /pelicula <título> — Carátula, cast, calidades + IA
• /estrenos — Próximas películas en YTS

📺 *Series (TVmaze):*
• /serie <título> — Carátula, info + torrents + IA

🎌 *Anime (MyAnimeList):*
• /anime <título> — Carátula, info + torrents + IA

🔍 *Búsqueda general:*
• /buscar <título> — Cualquier torrent vía Jackett + IA

📊 *Descargas:*
• /estado — Descargas activas en qBittorrent
• /historial — Últimas 10 descargas
• /stats — Estadísticas de uso

💳 *Suscripción:*
• /plan — Ver tu plan y obtener Premium

*Ejemplos:*
`/pelicula El Origen`
`/serie Breaking Bad`
`/anime Attack on Titan`
"""


@restricted
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # Log new users only once per session
    if user.id not in _seen_users:
        _seen_users.add(user.id)
        await storage.log_new_user(
            bot=context.bot,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
        )
    await update.message.reply_text(
        f"¡Hola, {user.first_name}! 👋\n" + HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
    )


@restricted
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)
