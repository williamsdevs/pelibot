"""
Telegram channel as persistent storage.

Logs: downloads, searches, new users, payments, errors.
Local db.json = fast lookup index.
"""
import json
import logging
import os
from datetime import datetime

from telegram import Bot

import config

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db.json")
_db: list[dict] = []


def _load() -> None:
    global _db
    if os.path.exists(_DB_PATH):
        try:
            with open(_DB_PATH, "r", encoding="utf-8") as f:
                _db = json.load(f)
            logger.info("Storage: %d registros cargados desde db.json", len(_db))
        except Exception as exc:
            logger.error("Error cargando db.json: %s", exc)
            _db = []
    else:
        _db = []


def _save() -> None:
    try:
        with open(_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(_db, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Error guardando db.json: %s", exc)


async def _post(bot: Bot, text: str) -> None:
    if not config.STORAGE_CHANNEL_ID:
        return
    try:
        await bot.send_message(
            chat_id=config.STORAGE_CHANNEL_ID,
            text=text,
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error("Error posteando al canal: %s", exc)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


def load_on_startup() -> None:
    _load()


# ── Downloads ────────────────────────────────────────────────────────────────

async def log_download(bot: Bot, title: str, magnet: str, size: str,
                       seeders: int, indexer: str, user_id: int, username: str) -> None:
    record = {
        "type": "download",
        "title": title,
        "magnet": magnet,
        "size": size,
        "seeders": seeders,
        "indexer": indexer,
        "user_id": user_id,
        "username": username or "desconocido",
        "date": _now(),
    }
    _db.append(record)
    _save()

    await _post(bot, (
        f"📥 *Nueva descarga*\n"
        f"🎬 *{title}*\n"
        f"📁 {size}  |  🌱 {seeders} seeds\n"
        f"📡 {indexer}\n"
        f"👤 @{username} (`{user_id}`)\n"
        f"🕐 {record['date']} UTC"
    ))


# ── Searches ─────────────────────────────────────────────────────────────────

async def log_search(bot: Bot, query: str, results_count: int,
                     user_id: int, username: str, search_type: str = "general") -> None:
    await _post(bot, (
        f"🔍 *Búsqueda* [{search_type}]\n"
        f"📝 `{query}`\n"
        f"📊 {results_count} resultados\n"
        f"👤 @{username} (`{user_id}`)\n"
        f"🕐 {_now()} UTC"
    ))


# ── New users ────────────────────────────────────────────────────────────────

async def log_new_user(bot: Bot, user_id: int, username: str, first_name: str) -> None:
    await _post(bot, (
        f"👤 *Nuevo usuario*\n"
        f"Nombre: {first_name}\n"
        f"Usuario: @{username}\n"
        f"ID: `{user_id}`\n"
        f"🕐 {_now()} UTC"
    ))


# ── Payments ─────────────────────────────────────────────────────────────────

async def log_payment(bot: Bot, user_id: int, username: str, stars: int) -> None:
    await _post(bot, (
        f"⭐ *Pago recibido*\n"
        f"👤 @{username} (`{user_id}`)\n"
        f"💰 {stars} Telegram Stars\n"
        f"📦 Premium 30 días activado\n"
        f"🕐 {_now()} UTC"
    ))


# ── Errors ───────────────────────────────────────────────────────────────────

async def log_error(bot: Bot, error: str, context: str = "") -> None:
    await _post(bot, (
        f"❌ *Error*\n"
        f"📍 {context}\n"
        f"⚠️ `{error[:300]}`\n"
        f"🕐 {_now()} UTC"
    ))


# ── Queries ──────────────────────────────────────────────────────────────────

def find_in_history(query: str) -> list[dict]:
    q = query.lower()
    return [r for r in _db if r.get("type") == "download" and q in r.get("title", "").lower()]


def get_recent(limit: int = 10) -> list[dict]:
    downloads = [r for r in _db if r.get("type") == "download"]
    return list(reversed(downloads[-limit:]))


def stats() -> dict:
    downloads = [r for r in _db if r.get("type") == "download"]
    return {
        "total": len(downloads),
        "users": len({r["user_id"] for r in downloads}),
    }
