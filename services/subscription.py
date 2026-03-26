"""Subscription and download limit management."""
import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger(__name__)

_SUB_PATH = os.path.join(os.path.dirname(__file__), "..", "subscriptions.json")

# Structure:
# {
#   "user_id": {
#     "premium_until": "2024-02-01",   # ISO date or null
#     "downloads": {
#       "2024-01": 3,   # month -> count
#     }
#   }
# }

_data: dict = {}


def load() -> None:
    global _data
    if os.path.exists(_SUB_PATH):
        try:
            with open(_SUB_PATH, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception as exc:
            logger.error("Error cargando subscriptions.json: %s", exc)
            _data = {}
    else:
        _data = {}


def _save() -> None:
    try:
        with open(_SUB_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Error guardando subscriptions.json: %s", exc)


def _user(user_id: int) -> dict:
    key = str(user_id)
    if key not in _data:
        _data[key] = {"premium_until": None, "downloads": {}}
    return _data[key]


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def is_premium(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    u = _user(user_id)
    if not u["premium_until"]:
        return False
    return datetime.utcnow().date().isoformat() <= u["premium_until"]


def downloads_this_month(user_id: int) -> int:
    if is_premium(user_id):
        return 0  # no limit
    month = datetime.utcnow().strftime("%Y-%m")
    return _user(user_id)["downloads"].get(month, 0)


def can_download(user_id: int) -> bool:
    if is_premium(user_id):
        return True
    return downloads_this_month(user_id) < config.FREE_DOWNLOADS_PER_MONTH


def record_download(user_id: int) -> None:
    if is_premium(user_id):
        return
    month = datetime.utcnow().strftime("%Y-%m")
    u = _user(user_id)
    u["downloads"][month] = u["downloads"].get(month, 0) + 1
    _save()


def activate_premium(user_id: int, days: int = 30) -> str:
    """Activate premium for user. Returns expiry date string."""
    from datetime import timedelta
    expiry = (datetime.utcnow().date() + timedelta(days=days)).isoformat()
    u = _user(user_id)
    # Extend if already premium
    if u["premium_until"] and u["premium_until"] > datetime.utcnow().date().isoformat():
        from datetime import date
        current = date.fromisoformat(u["premium_until"])
        expiry = (current + timedelta(days=days)).isoformat()
    u["premium_until"] = expiry
    _save()
    return expiry


def status(user_id: int) -> dict:
    if is_admin(user_id):
        return {"plan": "👑 Admin", "downloads_left": "∞", "premium_until": "Siempre"}
    if is_premium(user_id):
        return {
            "plan": "⭐ Premium",
            "downloads_left": "∞",
            "premium_until": _user(user_id)["premium_until"],
        }
    left = config.FREE_DOWNLOADS_PER_MONTH - downloads_this_month(user_id)
    return {
        "plan": "🆓 Gratuito",
        "downloads_left": max(0, left),
        "premium_until": None,
    }
