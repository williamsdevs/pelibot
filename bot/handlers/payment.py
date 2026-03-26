"""Handlers for /plan, /premium and Telegram Stars payments."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from bot.handlers.auth import restricted
from services import subscription


@restricted
async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/plan — show current subscription status."""
    user_id = update.effective_user.id
    s = subscription.status(user_id)

    if s["plan"] == "🆓 Gratuito":
        text = (
            f"📋 *Tu plan actual*\n\n"
            f"Plan: {s['plan']}\n"
            f"Descargas restantes este mes: *{s['downloads_left']}/{config.FREE_DOWNLOADS_PER_MONTH}*\n\n"
            f"Actualiza a Premium por solo *{config.PREMIUM_PRICE_STARS} ⭐ Stars/mes* "
            f"y descarga sin límites."
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Obtener Premium", callback_data="buy_premium")
        ]])
    elif s["plan"] == "⭐ Premium":
        text = (
            f"📋 *Tu plan actual*\n\n"
            f"Plan: {s['plan']}\n"
            f"Descargas: *Ilimitadas*\n"
            f"Válido hasta: *{s['premium_until']}*"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Renovar Premium", callback_data="buy_premium")
        ]])
    else:
        text = (
            f"📋 *Tu plan actual*\n\n"
            f"Plan: {s['plan']}\n"
            f"Descargas: *Ilimitadas* ♾️"
        )
        keyboard = None

    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def callback_buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Telegram Stars invoice."""
    query = update.callback_query
    await query.answer()

    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title="PeliBot Premium — 30 días",
        description=f"Descargas ilimitadas por 30 días. ({config.FREE_DOWNLOADS_PER_MONTH} gratis/mes en plan gratuito)",
        payload="premium_30days",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice("Premium 30 días", config.PREMIUM_PRICE_STARS)],
    )


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve all pre-checkout queries."""
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activate premium after successful payment."""
    from services import storage
    user = update.effective_user
    payment_info = update.message.successful_payment
    payload = payment_info.invoice_payload

    if payload == "premium_30days":
        expiry = subscription.activate_premium(user.id, days=30)
        await storage.log_payment(
            bot=context.bot,
            user_id=user.id,
            username=user.username or user.first_name,
            stars=payment_info.total_amount,
        )
        await update.message.reply_text(
            f"✅ *¡Premium activado!*\n\n"
            f"Disfruta de descargas ilimitadas hasta el *{expiry}*.\n"
            f"¡Gracias por tu apoyo! 🎉",
            parse_mode=ParseMode.MARKDOWN,
        )


def check_limit(user_id: int) -> bool:
    """Returns True if user can download, False if limit reached."""
    return subscription.can_download(user_id)


def limit_reached_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐ Obtener Premium", callback_data="buy_premium")
    ]])
