"""Handlers for /estado — show active downloads."""
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import qbittorrent

logger = logging.getLogger(__name__)


@restricted
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /estado — list active torrents."""
    try:
        torrents = await qbittorrent.get_torrents()
        transfer = await qbittorrent.get_torrent_speed()
    except Exception as exc:
        logger.error("qBittorrent error: %s", exc)
        await update.message.reply_text("❌ No se puede conectar con qBittorrent.")
        return

    if not torrents:
        await update.message.reply_text("📭 No hay torrents activos.")
        return

    dl_speed = transfer.get("dl_info_speed", 0) / (1024 ** 2)
    up_speed = transfer.get("up_info_speed", 0) / (1024 ** 2)

    lines = [f"📊 *Descargas activas* — ⬇️ {dl_speed:.2f} MB/s  ⬆️ {up_speed:.2f} MB/s\n"]
    for t in torrents[:15]:  # cap at 15 to avoid message length limits
        lines.append(qbittorrent.format_torrent_status(t))

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
