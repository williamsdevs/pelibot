"""TVmaze API client — free, no API key required."""
from dataclasses import dataclass, field

import aiohttp

_BASE = "https://api.tvmaze.com"


@dataclass
class TVShow:
    id: int
    name: str
    status: str        # Running, Ended, etc.
    premiered: str
    rating: float
    summary: str
    poster: str
    genres: list = field(default_factory=list)
    network: str = ""
    language: str = ""
    seasons: int = 0


def _parse_show(s: dict) -> TVShow:
    show = s.get("show", s)  # search returns {"score": x, "show": {...}}
    image = show.get("image") or {}
    network = show.get("network") or show.get("webChannel") or {}
    rating = (show.get("rating") or {}).get("average") or 0
    summary = (show.get("summary") or "").replace("<p>", "").replace("</p>", "").replace("<b>", "*").replace("</b>", "*")
    return TVShow(
        id=show.get("id", 0),
        name=show.get("name", "?"),
        status=show.get("status", ""),
        premiered=show.get("premiered") or "",
        rating=float(rating),
        summary=summary[:250],
        poster=image.get("medium", ""),
        genres=show.get("genres") or [],
        network=network.get("name", ""),
        language=show.get("language") or "",
    )


async def search(query: str) -> list:
    """Search TVmaze for shows matching query."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_BASE}/search/shows",
            params={"q": query},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
    return [_parse_show(item) for item in data]


async def show_details(show_id: int) -> TVShow:
    """Get full show details."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_BASE}/shows/{show_id}",
            params={"embed": "seasons"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
    show = _parse_show(data)
    seasons = data.get("_embedded", {}).get("seasons") or []
    show.seasons = len(seasons)
    return show
