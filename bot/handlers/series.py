"""Handler for /serie — search TV shows with poster via TVmaze + torrents via Jackett."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import tvmaze, jackett, qbittorrent, storage, ai

logger = logging.getLogger(__name__)

_SHOWS_KEY = "tvmaze_shows"
_TORRENTS_KEY = "serie_torrents"
_SHOW_IDX_KEY = "serie_show_idx"


@restricted
async def cmd_serie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Uso: /serie <título>\nEjemplo: /serie Breaking Bad")
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*…", parse_mode=ParseMode.MARKDOWN)

    try:
        shows = await tvmaze.search(query)
    except Exception as exc:
        logger.error("TVmaze error: %s", exc)
        await msg.edit_text("❌ Error al buscar la serie.")
        return

    if not shows:
        await msg.edit_text(f"🚫 Sin resultados para *{query}*", parse_mode=ParseMode.MARKDOWN)
        return

    context.user_data[_SHOWS_KEY] = shows
    await msg.delete()
    await _show_serie(update, context, index=0)


async def _show_serie(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    shows: list = context.user_data.get(_SHOWS_KEY, [])
    if index >= len(shows):
        return

    s: tvmaze.TVShow = shows[index]

    # Navigation
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"serie_nav:{index-1}"))
    if index < len(shows) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"serie_nav:{index+1}"))

    keyboard = InlineKeyboardMarkup(
        ([nav] if nav else [])
        + [[InlineKeyboardButton("🔍 Buscar torrents", callback_data=f"serie_torrents:{index}")]]
        + [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
    )

    genres = " · ".join(s.genres[:3]) if s.genres else ""
    status_emoji = "🟢" if s.status == "Running" else "🔴"
    meta_parts = list(filter(None, [
        s.premiered[:4] if s.premiered else "",
        genres,
        s.network,
        f"{s.seasons} temporadas" if s.seasons else "",
    ]))
    meta = "  |  ".join(meta_parts)

    caption = (
        f"📺 *{s.name}*\n"
        f"{status_emoji} {s.status}  |  ⭐ {s.rating}/10\n"
        + (f"_{meta}_\n\n" if meta else "\n")
        + (f"{s.summary}\n\n" if s.summary else "")
        + "¿Qué deseas hacer?"
    )

    if s.poster:
        await update.effective_message.reply_photo(
            photo=s.poster, caption=caption,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )
    else:
        await update.effective_message.reply_text(
            caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )


async def callback_serie_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    await query.delete_message()
    await _show_serie(update, context, index)


async def callback_serie_torrents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search Jackett for torrents of the selected show."""
    query = update.callback_query
    await query.answer("Buscando torrents…")

    index = int(query.data.split(":")[1])
    shows: list = context.user_data.get(_SHOWS_KEY, [])
    s: tvmaze.TVShow = shows[index]

    await query.edit_message_caption(
        caption=f"🔍 Buscando torrents de *{s.name}*…",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        results = await jackett.search(s.name, categories=[jackett_series_cat()])
    except Exception as exc:
        logger.error("Jackett error: %s", exc)
        await query.edit_message_caption(caption="❌ Error al conectar con Jackett.")
        return

    if not results:
        await query.edit_message_caption(
            caption=f"🚫 Sin torrents para *{s.name}*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    context.user_data[_TORRENTS_KEY] = results
    context.user_data[_SHOW_IDX_KEY] = index

    from bot.keyboards import torrent_list_keyboard
    lines = [f"📺 *{s.name}* — {len(results)} resultados\n"]
    for i, r in enumerate(results):
        lines.append(f"{i+1}. {r.title[:40]}\n   📁 {r.size_gb}  |  🌱 {r.seeders}")

    buttons = []
    for i, r in enumerate(results):
        buttons.append([InlineKeyboardButton(
            f"{i+1}. {r.title[:30]} | {r.size_gb} | {r.seeders}🌱",
            callback_data=f"serie_dl:{i}"
        )])
    buttons.append([InlineKeyboardButton("🤖 Elección automática con IA", callback_data="serie_ai")])
    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])

    await query.edit_message_caption(
        caption="\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def callback_serie_dl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show confirmation for selected torrent."""
    query = update.callback_query
    await query.answer()

    index = int(query.data.split(":")[1])
    results = context.user_data.get(_TORRENTS_KEY, [])
    if index >= len(results):
        await query.edit_message_caption(caption="❌ Resultado no encontrado.")
        return

    r = results[index]
    text = (
        f"📦 *{r.title}*\n\n"
        f"📁 {r.size_gb}  |  🌱 {r.seeders} seeds  |  🔽 {r.leechers}\n"
        f"📡 {r.indexer}\n\n"
        "¿Confirmas la descarga?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Descargar", callback_data=f"serie_confirm:{index}"),
        InlineKeyboardButton("🔙 Volver", callback_data=f"serie_torrents:{context.user_data.get(_SHOW_IDX_KEY, 0)}"),
    ]])
    await query.edit_message_caption(caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def callback_serie_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send torrent to qBittorrent."""
    from bot.handlers._download_guard import check_and_record
    query = update.callback_query
    await query.answer()
    if not await check_and_record(update, query.from_user.id):
        return

    index = int(query.data.split(":")[1])
    results = context.user_data.get(_TORRENTS_KEY, [])
    r = results[index]

    await query.edit_message_caption(
        caption=f"⏳ Añadiendo *{r.title}*…", parse_mode=ParseMode.MARKDOWN
    )

    try:
        ok = await qbittorrent.add_magnet(r.magnet)
    except Exception as exc:
        logger.error("qBittorrent error: %s", exc)
        await query.edit_message_caption(caption="❌ Error al conectar con qBittorrent.")
        return

    if ok:
        user = query.from_user
        await storage.log_download(
            bot=context.bot, title=r.title, magnet=r.magnet,
            size=r.size_gb, seeders=r.seeders, indexer=r.indexer,
            user_id=user.id, username=user.username or user.first_name,
        )
        await query.edit_message_caption(
            caption=f"✅ *{r.title}* añadido.\n\nUsa /estado para ver el progreso.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.edit_message_caption(caption="❌ qBittorrent rechazó el torrent.")


async def callback_serie_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """AI picks the best torrent for the series."""
    query = update.callback_query
    await query.answer("🤖 Consultando a la IA…")

    shows: list = context.user_data.get(_SHOWS_KEY, [])
    show_idx = context.user_data.get(_SHOW_IDX_KEY, 0)
    results = context.user_data.get(_TORRENTS_KEY, [])
    show_name = shows[show_idx].name if shows else "serie"

    await query.edit_message_caption(caption="🤖 La IA está eligiendo el mejor torrent…")

    index, reason = await ai.pick_best_torrent(show_name, results)
    r = results[index]

    text = (
        f"🤖 *La IA eligió:*\n\n"
        f"📦 *{r.title}*\n"
        f"📁 {r.size_gb}  |  🌱 {r.seeders} seeds\n"
        f"📡 {r.indexer}\n\n"
        f"💬 _{reason}_\n\n"
        "¿Confirmas la descarga?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Descargar", callback_data=f"serie_confirm:{index}"),
        InlineKeyboardButton("🔙 Volver", callback_data=f"serie_torrents:{show_idx}"),
    ]])
    await query.edit_message_caption(caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


def jackett_series_cat():
    return "5000"
