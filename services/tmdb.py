"""TMDB client for movie/series metadata (optional)."""
import aiohttp

import config

_BASE = "https://api.themoviedb.org/3"
_IMG_BASE = "https://image.tmdb.org/t/p/w500"


async def search_movie(query: str):
    """Return first TMDB movie result or None if TMDB is not configured."""
    if not config.TMDB_API_KEY:
        return None

    params = {"api_key": config.TMDB_API_KEY, "query": query, "language": "es-ES"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_BASE}/search/multi", params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()

    results = data.get("results", [])
    return results[0] if results else None


def poster_url(path):
    if not path:
        return None
    return f"{_IMG_BASE}{path}"
