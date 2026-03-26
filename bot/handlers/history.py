"""Handlers for /historial and /stats."""
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import storage


@restricted
async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/historial — show recent downloads."""
    recent = storage.get_recent(10)

    if not recent:
        await update.message.reply_text("📭 Aún no hay descargas registradas.")
        return

    lines = ["📋 *Últimas descargas:*\n"]
    for i, r in enumerate(recent, 1):
        lines.append(
            f"{i}. *{r['title']}*\n"
            f"   📁 {r['size']}  |  👤 @{r['username']}  |  🕐 {r['date']}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@restricted
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — show download statistics."""
    s = storage.stats()
    await update.message.reply_text(
        f"📊 *Estadísticas*\n\n"
        f"🎬 Total descargas: *{s['total']}*\n"
        f"👥 Usuarios distintos: *{s['users']}*",
        parse_mode=ParseMode.MARKDOWN,
    )
