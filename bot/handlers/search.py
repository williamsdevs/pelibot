"""Handlers for /buscar and torrent selection flow."""
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from bot.handlers.auth import restricted
from bot.keyboards import confirm_keyboard, torrent_list_keyboard
from services import jackett, tmdb, storage

logger = logging.getLogger(__name__)

# Context key where search results are stored between interactions
_RESULTS_KEY = "search_results"
# Context key for the last search query
_QUERY_KEY = "last_query"


@restricted
async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buscar <title> — search torrents."""
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text(
            "Uso: /buscar <título>\nEjemplo: /buscar Breaking Bad"
        )
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*…", parse_mode=ParseMode.MARKDOWN)

    # Fetch TMDB info in parallel with torrent search (optional)
    try:
        results, meta = await _parallel_search(query)
    except Exception as exc:
        logger.error("Search error: %s", exc)
        await msg.edit_text("❌ Error al conectar con Jackett. ¿Está corriendo?")
        return

    if not results:
        await msg.edit_text(f'🚫 Sin resultados para *{query}*', parse_mode=ParseMode.MARKDOWN)
        return

    context.user_data[_RESULTS_KEY] = results
    context.user_data[_QUERY_KEY] = query

    await storage.log_search(
        bot=context.bot, query=query, results_count=len(results),
        user_id=update.effective_user.id,
        username=update.effective_user.username or update.effective_user.first_name,
        search_type="general",
    )

    caption = _build_caption(query, meta, len(results))
    keyboard = torrent_list_keyboard(results)

    if meta and meta.get("poster_path") and config.TMDB_API_KEY:
        poster = tmdb.poster_url(meta["poster_path"])
        await msg.delete()
        await update.message.reply_photo(
            photo=poster,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    else:
        await msg.edit_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def _parallel_search(query: str):
    import asyncio
    results_coro = jackett.search(query)
    meta_coro = tmdb.search_movie(query)
    results, meta = await asyncio.gather(results_coro, meta_coro, return_exceptions=True)
    if isinstance(results, Exception):
        raise results
    if isinstance(meta, Exception):
        meta = None
    return results, meta


def _build_caption(query: str, meta, count: int) -> str:
    title = query
    overview = ""
    if meta:
        title = meta.get("title") or meta.get("name") or query
        overview = meta.get("overview", "")
        if overview:
            overview = f"\n_{overview[:200]}_\n"

    return (
        f"🎬 *{title}*{overview}\n"
        f"Se encontraron *{count}* resultados. Elige uno:"
    )


async def callback_torrent_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User tapped on a torrent — show confirmation."""
    query = update.callback_query
    await query.answer()

    index = int(query.data.split(":")[1])
    results: list = context.user_data.get(_RESULTS_KEY, [])

    if index >= len(results):
        await query.edit_message_text("❌ Resultado no encontrado. Busca de nuevo.")
        return

    r = results[index]
    text = (
        f"📦 *{r.title}*\n\n"
        f"📁 Tamaño: {r.size_gb}\n"
        f"🌱 Seeds: {r.seeders}  🔽 Peers: {r.leechers}\n"
        f"🗂 Categoría: {r.category}\n"
        f"📡 Indexer: {r.indexer}\n\n"
        "¿Confirmas la descarga?"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=confirm_keyboard(index))


async def callback_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User confirmed download — send magnet to qBittorrent."""
    from services import qbittorrent
    from bot.handlers._download_guard import check_and_record

    query = update.callback_query
    await query.answer()

    if not await check_and_record(update, query.from_user.id):
        return

    index = int(query.data.split(":")[1])
    results: list = context.user_data.get(_RESULTS_KEY, [])

    if index >= len(results):
        await query.edit_message_text("❌ Resultado no encontrado.")
        return

    r = results[index]
    await query.edit_message_text(f"⏳ Añadiendo *{r.title}* a qBittorrent…", parse_mode=ParseMode.MARKDOWN)

    try:
        ok = await qbittorrent.add_magnet(r.magnet)
    except Exception as exc:
        logger.error("qBittorrent error: %s", exc)
        await query.edit_message_text("❌ Error al conectar con qBittorrent. ¿Está corriendo?")
        return

    if ok:
        # Log to Telegram storage channel
        from services import storage
        user = query.from_user
        await storage.log_download(
            bot=context.bot,
            title=r.title,
            magnet=r.magnet,
            size=r.size_gb,
            seeders=r.seeders,
            indexer=r.indexer,
            user_id=user.id,
            username=user.username or user.first_name,
        )
        await query.edit_message_text(
            f"✅ *{r.title}* añadido a la cola de descarga.\n\nUsa /estado para ver el progreso.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.edit_message_text("❌ qBittorrent rechazó el torrent. Revisa los logs.")


async def callback_ai_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Let Groq AI pick the best torrent automatically."""
    from services import ai, qbittorrent

    query = update.callback_query
    await query.answer("🤖 Consultando a la IA…")

    results: list = context.user_data.get(_RESULTS_KEY, [])
    search_query: str = context.user_data.get(_QUERY_KEY, "")

    if not results:
        await query.edit_message_text("No hay resultados. Usa /buscar de nuevo.")
        return

    await query.edit_message_text("🤖 La IA está eligiendo el mejor torrent…", parse_mode=ParseMode.MARKDOWN)

    index, reason = await ai.pick_best_torrent(search_query, results)
    r = results[index]

    text = (
        f"🤖 *La IA eligió:*\n\n"
        f"📦 *{r.title}*\n"
        f"📁 {r.size_gb}  |  🌱 {r.seeders} seeds\n"
        f"📡 {r.indexer}\n\n"
        f"💬 _{reason}_\n\n"
        "¿Confirmas la descarga?"
    )
    from bot.keyboards import confirm_keyboard
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=confirm_keyboard(index))


async def callback_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Búsqueda cancelada.")


async def callback_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to results list."""
    query = update.callback_query
    await query.answer()

    results = context.user_data.get(_RESULTS_KEY, [])
    search_query = context.user_data.get(_QUERY_KEY, "")

    if not results:
        await query.edit_message_text("No hay resultados guardados. Usa /buscar.")
        return

    caption = _build_caption(search_query, None, len(results))
    await query.edit_message_text(
        caption,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=torrent_list_keyboard(results),
    )
