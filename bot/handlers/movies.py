"""Handlers for /pelicula and /estrenos — YTS movies with posters."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import restricted
from services import yts, qbittorrent, storage

logger = logging.getLogger(__name__)

_MOVIES_KEY = "yts_movies"


# ── /pelicula ────────────────────────────────────────────────────────────────

@restricted
async def cmd_pelicula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Uso: /pelicula <título>\nEjemplo: /pelicula Inception")
        return

    msg = await update.message.reply_text(f"🔍 Buscando *{query}*…", parse_mode=ParseMode.MARKDOWN)

    try:
        movies = await yts.search(query)
    except Exception as exc:
        logger.error("YTS error: %s", exc)
        await msg.edit_text("❌ Error al conectar con YTS.")
        return

    if not movies:
        await msg.edit_text(
            f"🚫 Sin resultados en YTS para *{query}*\nPrueba con /buscar para series.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    context.user_data[_MOVIES_KEY] = movies
    await msg.delete()
    await _show_movie(update, context, index=0)


async def _show_movie(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    movies: list = context.user_data.get(_MOVIES_KEY, [])
    if index >= len(movies):
        return

    m: yts.YTSMovie = movies[index]

    # Quality buttons
    quality_btns = [
        InlineKeyboardButton(
            f"{'🏆' if i == 0 else '📀'} {t['quality']} — {t['size']} ({t['seeds']}🌱)",
            callback_data=f"yts_dl:{index}:{i}",
        )
        for i, t in enumerate(m.torrents)
    ]

    # Navigation
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"yts_nav:{index-1}"))
    if index < len(movies) - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"yts_nav:{index+1}"))

    keyboard = InlineKeyboardMarkup(
        [[b] for b in quality_btns]
        + ([nav] if nav else [])
        + [[InlineKeyboardButton("🎬 Ver cast & detalles", callback_data=f"yts_detail:{index}")]]
        + [[InlineKeyboardButton("🔀 Películas similares", callback_data=f"yts_suggest:{index}")]]
        + [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]]
    )

    genres = " · ".join(m.genres[:3]) if m.genres else ""
    runtime = f"{m.runtime} min" if m.runtime else ""
    meta = " | ".join(filter(None, [genres, runtime, m.language.upper() if m.language else ""]))

    caption = (
        f"🎬 *{m.title}* ({m.year})\n"
        f"⭐ {m.rating}/10"
        + (f"  |  {meta}" if meta else "") + "\n\n"
        + (f"_{m.summary}_\n\n" if m.summary else "")
        + "Elige la calidad:"
    )

    if m.poster:
        await update.effective_message.reply_photo(
            photo=m.poster, caption=caption,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )
    else:
        await update.effective_message.reply_text(
            caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )


# ── /estrenos ────────────────────────────────────────────────────────────────

@restricted
async def cmd_estrenos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("🎬 Cargando próximos estrenos…")
    try:
        upcoming = await yts.upcoming()
    except Exception as exc:
        logger.error("YTS upcoming error: %s", exc)
        await msg.edit_text("❌ Error al obtener estrenos.")
        return

    if not upcoming:
        await msg.edit_text("📭 No hay estrenos disponibles en este momento.")
        return

    await msg.delete()
    for m in upcoming:
        genres = " · ".join(m.genres[:3]) if m.genres else ""
        caption = (
            f"🎬 *{m.title}* ({m.year})\n"
            f"⭐ {m.rating}/10" + (f"  |  {genres}" if genres else "") + "\n\n"
            + (f"_{m.summary}_" if m.summary else "Próximamente en YTS")
        )
        if m.poster:
            await update.message.reply_photo(photo=m.poster, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)


# ── Callbacks ────────────────────────────────────────────────────────────────

async def callback_yts_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    await query.delete_message()
    await _show_movie(update, context, index)


async def callback_yts_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show full cast and details."""
    query = update.callback_query
    await query.answer("Cargando detalles…")

    index = int(query.data.split(":")[1])
    movies: list = context.user_data.get(_MOVIES_KEY, [])
    m: yts.YTSMovie = movies[index]

    try:
        detailed = await yts.movie_details(m.id)
    except Exception as exc:
        logger.error("YTS detail error: %s", exc)
        await query.answer("❌ Error al cargar detalles.", show_alert=True)
        return

    cast_lines = ""
    if detailed.cast:
        cast_lines = "\n👥 *Cast:*\n" + "\n".join(
            f"  • {a['name']}" + (f" → _{a['character']}_" if a['character'] else "")
            for a in detailed.cast[:6]
        )

    genres = " · ".join(detailed.genres) if detailed.genres else ""
    runtime = f"{detailed.runtime} min" if detailed.runtime else ""

    text = (
        f"🎬 *{detailed.title}* ({detailed.year})\n"
        f"⭐ {detailed.rating}/10  |  {genres}\n"
        f"⏱ {runtime}\n\n"
        f"_{detailed.summary}_"
        f"{cast_lines}"
    )

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data=f"yts_nav:{index}")]])
    await query.edit_message_caption(caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def callback_yts_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show similar movies."""
    query = update.callback_query
    await query.answer("Buscando similares…")

    index = int(query.data.split(":")[1])
    movies: list = context.user_data.get(_MOVIES_KEY, [])
    m: yts.YTSMovie = movies[index]

    try:
        similar = await yts.suggestions(m.id)
    except Exception as exc:
        logger.error("YTS suggestions error: %s", exc)
        await query.answer("❌ Error al cargar sugerencias.", show_alert=True)
        return

    if not similar:
        await query.answer("No hay sugerencias disponibles.", show_alert=True)
        return

    # Replace the current results with suggestions
    context.user_data[_MOVIES_KEY] = similar
    await query.delete_message()
    await _show_movie(update, context, index=0)


async def callback_yts_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers._download_guard import check_and_record
    query = update.callback_query
    await query.answer()
    if not await check_and_record(update, query.from_user.id):
        return

    _, movie_idx, torrent_idx = query.data.split(":")
    movies: list = context.user_data.get(_MOVIES_KEY, [])
    m: yts.YTSMovie = movies[int(movie_idx)]
    t = m.torrents[int(torrent_idx)]
    magnet = m.magnet(t)

    await query.edit_message_caption(
        caption=f"⏳ Añadiendo *{m.title}* [{t['quality']}] a qBittorrent…",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        ok = await qbittorrent.add_magnet(magnet)
    except Exception as exc:
        logger.error("qBittorrent error: %s", exc)
        await query.edit_message_caption(caption="❌ Error al conectar con qBittorrent.")
        return

    if ok:
        user = query.from_user
        await storage.log_download(
            bot=context.bot,
            title=f"{m.title} ({m.year}) [{t['quality']}]",
            magnet=magnet,
            size=t["size"],
            seeders=t["seeds"],
            indexer="YTS",
            user_id=user.id,
            username=user.username or user.first_name,
        )
        await query.edit_message_caption(
            caption=(
                f"✅ *{m.title}* [{t['quality']}] añadido.\n\n"
                f"Usa /estado para ver el progreso."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.edit_message_caption(caption="❌ qBittorrent rechazó el torrent.")
