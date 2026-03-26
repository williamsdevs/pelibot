"""YTS API client — movies with posters, details, suggestions and upcoming."""
from dataclasses import dataclass, field

import aiohttp

_BASE = "https://movies-api.accel.li/api/v2"

_TRACKERS = [
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:80",
    "udp://tracker.coppersurfer.tk:6969",
    "udp://glotorrents.pw:6969/announce",
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://torrent.gresille.org:80/announce",
    "udp://p4p.arenabg.com:1337",
    "udp://tracker.leechers-paradise.org:6969",
]


@dataclass
class YTSMovie:
    id: int
    title: str
    year: int
    rating: float
    summary: str
    poster: str
    genres: list = field(default_factory=list)
    runtime: int = 0          # minutes
    language: str = ""
    cast: list = field(default_factory=list)   # [{name, character, url_small_image}]
    torrents: list = field(default_factory=list)

    def best_torrent(self):
        if not self.torrents:
            return None
        return max(self.torrents, key=lambda t: t.get("seeds", 0))

    def magnet(self, torrent: dict) -> str:
        hash_ = torrent["hash"]
        name = f"{self.title} ({self.year})"
        trackers = "&tr=".join(_TRACKERS)
        return f"magnet:?xt=urn:btih:{hash_}&dn={name}&tr={trackers}"


def _parse_movie(m: dict, with_cast: bool = False) -> YTSMovie:
    torrents = [
        {
            "quality": t.get("quality", "?"),
            "size": t.get("size", "?"),
            "seeds": t.get("seeds", 0),
            "peers": t.get("peers", 0),
            "hash": t.get("hash", ""),
        }
        for t in m.get("torrents") or []
    ]
    cast = []
    if with_cast:
        cast = [
            {
                "name": a.get("name", ""),
                "character": a.get("character_name", ""),
                "photo": a.get("url_small_image", ""),
            }
            for a in m.get("cast") or []
        ]
    return YTSMovie(
        id=m.get("id", 0),
        title=m.get("title", "?"),
        year=m.get("year", 0),
        rating=m.get("rating", 0),
        summary=(m.get("summary") or "")[:250],
        poster=m.get("medium_cover_image", ""),
        genres=m.get("genres") or [],
        runtime=m.get("runtime", 0),
        language=m.get("language", ""),
        cast=cast,
        torrents=torrents,
    )


async def _get(endpoint: str, params: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_BASE}/{endpoint}",
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            return await resp.json()


def _translate_to_english(text: str) -> str:
    """Translate text to English using Google Translate (free, no API key)."""
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target="en").translate(text)
        return translated or text
    except Exception:
        return text


async def search(query: str, limit: int = 8) -> list:
    """Search YTS for movies matching query. Auto-translates to English if needed."""
    import asyncio

    # Try original query first
    data = await _get("list_movies.json", {"query_term": query, "limit": limit, "sort_by": "seeds"})
    movies = data.get("data", {}).get("movies") or []

    # If no results, translate to English and retry
    if not movies:
        translated = await asyncio.get_event_loop().run_in_executor(None, _translate_to_english, query)
        if translated.lower() != query.lower():
            data = await _get("list_movies.json", {"query_term": translated, "limit": limit, "sort_by": "seeds"})
            movies = data.get("data", {}).get("movies") or []

    return [_parse_movie(m) for m in movies]


async def movie_details(movie_id: int) -> YTSMovie:
    """Get full details including cast for a specific movie."""
    data = await _get("movie_details.json", {"movie_id": movie_id, "with_images": True, "with_cast": True})
    return _parse_movie(data.get("data", {}).get("movie", {}), with_cast=True)


async def suggestions(movie_id: int) -> list:
    """Get 4 similar movie suggestions."""
    data = await _get("movie_suggestions.json", {"movie_id": movie_id})
    return [_parse_movie(m) for m in data.get("data", {}).get("movies") or []]


async def upcoming() -> list:
    """Get the 4 latest upcoming movies."""
    data = await _get("list_upcoming.json", {})
    return [_parse_movie(m) for m in data.get("data", {}).get("upcoming") or []]
