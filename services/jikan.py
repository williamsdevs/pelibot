"""Jikan API client — MyAnimeList data, free, no API key."""
from dataclasses import dataclass, field

import aiohttp

_BASE = "https://api.jikan.moe/v4"


@dataclass
class Anime:
    id: int
    title: str
    title_en: str
    episodes: int
    status: str
    score: float
    synopsis: str
    poster: str
    genres: list = field(default_factory=list)
    year: int = 0
    season: str = ""
    type: str = ""   # TV, Movie, OVA, etc.


def _parse(a: dict) -> Anime:
    titles = {t["type"]: t["title"] for t in a.get("titles", [])}
    images = a.get("images", {}).get("jpg", {})
    genres = [g["name"] for g in a.get("genres", [])]
    return Anime(
        id=a.get("mal_id", 0),
        title=a.get("title", "?"),
        title_en=titles.get("English", "") or a.get("title_english", ""),
        episodes=a.get("episodes") or 0,
        status=a.get("status", ""),
        score=float(a.get("score") or 0),
        synopsis=(a.get("synopsis") or "")[:250],
        poster=images.get("image_url", ""),
        genres=genres,
        year=a.get("year") or 0,
        season=a.get("season") or "",
        type=a.get("type") or "",
    )


async def search(query: str) -> list:
    """Search MyAnimeList for anime matching query."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_BASE}/anime",
            params={"q": query, "limit": 8, "order_by": "score", "sort": "desc"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
    return [_parse(a) for a in data.get("data", [])]
