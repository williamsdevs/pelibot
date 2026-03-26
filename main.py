"""PeliBot — Telegram bot for downloading movies and series via qBittorrent."""
import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)

import config
from bot.handlers import general, search, status, history, movies, series, anime, payment
from services import storage, subscription

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update, context) -> None:
    # Ignore errors from edited messages (update.message is None)
    if update and getattr(update, "edited_message", None):
        return
    logger.error("Error: %s", context.error)
    try:
        await storage.log_error(
            bot=context.bot,
            error=str(context.error),
            context=f"{type(context.error).__name__}",
        )
    except Exception:
        pass


def main() -> None:
    storage.load_on_startup()
    subscription.load()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", general.cmd_start))
    app.add_handler(CommandHandler("ayuda", general.cmd_ayuda))
    app.add_handler(CommandHandler("buscar", search.cmd_buscar))
    app.add_handler(CommandHandler("estado", status.cmd_estado))
    app.add_handler(CommandHandler("historial", history.cmd_historial))
    app.add_handler(CommandHandler("stats", history.cmd_stats))
    app.add_handler(CommandHandler("pelicula", movies.cmd_pelicula))
    app.add_handler(CommandHandler("estrenos", movies.cmd_estrenos))
    app.add_handler(CommandHandler("plan", payment.cmd_plan))
    app.add_handler(CommandHandler("serie", series.cmd_serie))
    app.add_handler(CommandHandler("anime", anime.cmd_anime))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(search.callback_torrent_selected, pattern=r"^dl:\d+$"))
    app.add_handler(CallbackQueryHandler(search.callback_confirm, pattern=r"^confirm:\d+$"))
    app.add_handler(CallbackQueryHandler(payment.callback_buy_premium, pattern=r"^buy_premium$"))
    app.add_handler(PreCheckoutQueryHandler(payment.pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment.successful_payment))
    app.add_handler(CallbackQueryHandler(search.callback_ai_pick, pattern=r"^ai_pick$"))
    app.add_handler(CallbackQueryHandler(search.callback_cancel, pattern=r"^cancel$"))
    app.add_handler(CallbackQueryHandler(search.callback_back, pattern=r"^back$"))
    app.add_handler(CallbackQueryHandler(movies.callback_yts_nav, pattern=r"^yts_nav:\d+$"))
    app.add_handler(CallbackQueryHandler(movies.callback_yts_download, pattern=r"^yts_dl:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(movies.callback_yts_detail, pattern=r"^yts_detail:\d+$"))
    app.add_handler(CallbackQueryHandler(movies.callback_yts_suggest, pattern=r"^yts_suggest:\d+$"))
    # Series
    app.add_handler(CallbackQueryHandler(series.callback_serie_nav, pattern=r"^serie_nav:\d+$"))
    app.add_handler(CallbackQueryHandler(series.callback_serie_torrents, pattern=r"^serie_torrents:\d+$"))
    app.add_handler(CallbackQueryHandler(series.callback_serie_dl, pattern=r"^serie_dl:\d+$"))
    app.add_handler(CallbackQueryHandler(series.callback_serie_confirm, pattern=r"^serie_confirm:\d+$"))
    app.add_handler(CallbackQueryHandler(series.callback_serie_ai, pattern=r"^serie_ai$"))
    # Anime
    app.add_handler(CallbackQueryHandler(anime.callback_anime_nav, pattern=r"^anime_nav:\d+$"))
    app.add_handler(CallbackQueryHandler(anime.callback_anime_torrents, pattern=r"^anime_torrents:\d+$"))
    app.add_handler(CallbackQueryHandler(anime.callback_anime_dl, pattern=r"^anime_dl:\d+$"))
    app.add_handler(CallbackQueryHandler(anime.callback_anime_confirm, pattern=r"^anime_confirm:\d+$"))
    app.add_handler(CallbackQueryHandler(anime.callback_anime_ai, pattern=r"^anime_ai$"))

    app.add_error_handler(error_handler)

    logger.info("PeliBot iniciado. Esperando mensajes…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
