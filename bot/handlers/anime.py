"""Handler for /anime — search anime with poster via Jikan (MAL) + torrents via Jackett."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import jikan, jackett, qbittorrent, storage, ai

logger = logging.getLogger(__name__)

_ANIME_KEY = "jikan_anime"
_TORRENTS_KEY = "anime_torrents"
_ANIME_IDX_KEY = "anime_idx"


@restricted
async def cmd_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Uso: /anime <título>\nEjemplo: /anime Attack on Titan")
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*…", parse_mode=ParseMode.MARKDOWN)

    try:
        results = await jikan.search(query)
    except Exception as exc:
        logger.error("Jikan error: %s", exc)
        await msg.edit_text("❌ Error al buscar en MyAnimeList.")
        return

    if not results:
        await msg.edit_text(f"🚫 Sin resultados para *{query}*", parse_mode=ParseMode.MARKDOWN)
        return

    context.user_data[_ANIME_KEY] = results
    await msg.delete()
    await _show_anime(update, context, index=0)


async def _show_anime(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    results: list = context.user_data.get(_ANIME_KEY, [])
    if index >= len(results):
        return

    a: jikan.Anime = results[index]

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"anime_nav:{index-1}"))
    if index < len(results) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"anime_nav:{index+1}"))

    keyboard = InlineKeyboardMarkup(
        ([nav] if nav else [])
        + [[InlineKeyboardButton("🔍 Buscar torrents", callback_data=f"anime_torrents:{index}")]]
        + [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
    )

    genres = " · ".join(a.genres[:4]) if a.genres else ""
    title_en = f" _{a.title_en}_" if a.title_en and a.title_en != a.title else ""
    meta_parts = list(filter(None, [
        str(a.year) if a.year else "",
        a.type,
        f"{a.episodes} eps" if a.episodes else "",
        a.season.capitalize() if a.season else "",
    ]))
    meta = "  |  ".join(meta_parts)
    status_emoji = "🟢" if "Airing" in a.status else "🔴"

    caption = (
        f"🎌 *{a.title}*{title_en}\n"
        f"{status_emoji} {a.status}  |  ⭐ {a.score}/10\n"
        + (f"_{meta}_\n" if meta else "")
        + (f"_{genres}_\n\n" if genres else "\n")
        + (f"{a.synopsis}\n\n" if a.synopsis else "")
        + "¿Qué deseas hacer?"
    )

    if a.poster:
        await update.effective_message.reply_photo(
            photo=a.poster, caption=caption,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )
    else:
        await update.effective_message.reply_text(
            caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )


async def callback_anime_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    await query.delete_message()
    await _show_anime(update, context, index)


async def callback_anime_torrents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Buscando torrents…")

    index = int(query.data.split(":")[1])
    anime_list: list = context.user_data.get(_ANIME_KEY, [])
    a: jikan.Anime = anime_list[index]

    search_term = a.title_en if a.title_en else a.title
    await query.edit_message_caption(
        caption=f"🔍 Buscando torrents de *{a.title}*…", parse_mode=ParseMode.MARKDOWN
    )

    try:
        torrents = await jackett.search(search_term, categories=["5070"])
    except Exception as exc:
        logger.error("Jackett error: %s", exc)
        await query.edit_message_caption(caption="❌ Error al conectar con Jackett.")
        return

    if not torrents:
        # Retry with original Japanese title
        try:
            torrents = await jackett.search(a.title, categories=["5070"])
        except Exception:
            pass

    if not torrents:
        await query.edit_message_caption(
            caption=f"🚫 Sin torrents para *{a.title}*", parse_mode=ParseMode.MARKDOWN
        )
        return

    context.user_data[_TORRENTS_KEY] = torrents
    context.user_data[_ANIME_IDX_KEY] = index

    lines = [f"🎌 *{a.title}* — {len(torrents)} resultados\n"]
    for i, r in enumerate(torrents):
        lines.append(f"{i+1}. {r.title[:40]}\n   📁 {r.size_gb}  |  🌱 {r.seeders}")

    buttons = []
    for i, r in enumerate(torrents):
        buttons.append([InlineKeyboardButton(
            f"{i+1}. {r.title[:30]} | {r.size_gb} | {r.seeders}🌱",
            callback_data=f"anime_dl:{i}"
        )])
    buttons.append([InlineKeyboardButton("🤖 Elección automática con IA", callback_data="anime_ai")])
    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])

    await query.edit_message_caption(
        caption="\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def callback_anime_dl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    index = int(query.data.split(":")[1])
    torrents = context.user_data.get(_TORRENTS_KEY, [])
    r = torrents[index]
    anime_idx = context.user_data.get(_ANIME_IDX_KEY, 0)

    text = (
        f"📦 *{r.title}*\n\n"
        f"📁 {r.size_gb}  |  🌱 {r.seeders} seeds\n"
        f"📡 {r.indexer}\n\n"
        "¿Confirmas la descarga?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Descargar", callback_data=f"anime_confirm:{index}"),
        InlineKeyboardButton("🔙 Volver", callback_data=f"anime_torrents:{anime_idx}"),
    ]])
    await query.edit_message_caption(caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def callback_anime_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers._download_guard import check_and_record
    query = update.callback_query
    await query.answer()
    if not await check_and_record(update, query.from_user.id):
        return

    index = int(query.data.split(":")[1])
    torrents = context.user_data.get(_TORRENTS_KEY, [])
    r = torrents[index]

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


async def callback_anime_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("🤖 Consultando a la IA…")

    anime_list: list = context.user_data.get(_ANIME_KEY, [])
    anime_idx = context.user_data.get(_ANIME_IDX_KEY, 0)
    torrents = context.user_data.get(_TORRENTS_KEY, [])
    title = anime_list[anime_idx].title if anime_list else "anime"

    await query.edit_message_caption(caption="🤖 La IA está eligiendo el mejor torrent…")

    index, reason = await ai.pick_best_torrent(title, torrents)
    r = torrents[index]

    text = (
        f"🤖 *La IA eligió:*\n\n"
        f"📦 *{r.title}*\n"
        f"📁 {r.size_gb}  |  🌱 {r.seeders} seeds\n"
        f"📡 {r.indexer}\n\n"
        f"💬 _{reason}_\n\n"
        "¿Confirmas la descarga?"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Descargar", callback_data=f"anime_confirm:{index}"),
        InlineKeyboardButton("🔙 Volver", callback_data=f"anime_torrents:{anime_idx}"),
    ]])
    await query.edit_message_caption(caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
