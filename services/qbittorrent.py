"""qBittorrent Web API client (async via aiohttp)."""
import aiohttp

import config

_QB_URL = f"{config.QB_HOST}:{config.QB_PORT}"


async def _get_session() -> aiohttp.ClientSession:
    """Create an authenticated aiohttp session with qBittorrent."""
    session = aiohttp.ClientSession()
    await session.post(
        f"{_QB_URL}/api/v2/auth/login",
        data={"username": config.QB_USERNAME, "password": config.QB_PASSWORD},
    )
    return session


async def add_magnet(magnet: str, save_path=None) -> bool:
    """Add a magnet link to qBittorrent. Returns True on success."""
    async with await _get_session() as session:
        data = {"urls": magnet}
        if save_path or config.QB_DOWNLOAD_PATH:
            data["savepath"] = save_path or config.QB_DOWNLOAD_PATH

        async with session.post(
            f"{_QB_URL}/api/v2/torrents/add",
            data=data,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            text = await resp.text()
            return text.strip() == "Ok."


async def get_torrents() -> list:
    """Return list of all torrents with their status."""
    async with await _get_session() as session:
        async with session.get(
            f"{_QB_URL}/api/v2/torrents/info",
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            return await resp.json()


async def get_torrent_speed() -> dict:
    """Return global transfer info (speeds, ratio, etc.)."""
    async with await _get_session() as session:
        async with session.get(
            f"{_QB_URL}/api/v2/transfer/info",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return await resp.json()


def format_torrent_status(torrent: dict) -> str:
    """Format a torrent dict into a human-readable status line."""
    name = torrent.get("name", "?")[:40]
    state = torrent.get("state", "?")
    progress = torrent.get("progress", 0) * 100
    dlspeed = torrent.get("dlspeed", 0) / (1024 ** 2)  # MB/s
    size = torrent.get("size", 0) / (1024 ** 3)  # GB
    eta = torrent.get("eta", 0)

    state_emoji = {
        "downloading": "⬇️",
        "stalledDL": "⏸",
        "uploading": "⬆️",
        "pausedDL": "⏸",
        "pausedUP": "✅",
        "checkingDL": "🔍",
        "error": "❌",
        "missingFiles": "⚠️",
        "queuedDL": "🕐",
    }.get(state, "❓")

    eta_str = ""
    if eta > 0 and eta < 8640000:
        h, remainder = divmod(eta, 3600)
        m, s = divmod(remainder, 60)
        eta_str = f" ETA: {h}h{m}m" if h else f" ETA: {m}m{s}s"

    return (
        f"{state_emoji} *{name}*\n"
        f"   {progress:.1f}% de {size:.2f}GB — {dlspeed:.2f} MB/s{eta_str}"
    )
