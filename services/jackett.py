"""Jackett torrent search client."""
from dataclasses import dataclass

import aiohttp

import config


@dataclass
class TorrentResult:
    title: str
    size: int          # bytes
    seeders: int
    leechers: int
    magnet: str
    info_url: str
    category: str
    indexer: str

    @property
    def size_gb(self) -> str:
        gb = self.size / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.2f} GB"
        mb = self.size / (1024 ** 2)
        return f"{mb:.0f} MB"


async def search(query: str, categories=None) -> list:
    """Search Jackett for torrents matching query."""
    params = {
        "apikey": config.JACKETT_API_KEY,
        "Query": query,
        "t": "search",
    }
    if categories:
        params["cat"] = ",".join(categories)

    url = f"{config.JACKETT_URL}/api/v2.0/indexers/all/results"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    results = []
    for item in data.get("Results", []):
        magnet = item.get("MagnetUri") or ""
        if not magnet:
            continue  # skip results without magnet link
        results.append(TorrentResult(
            title=item.get("Title", "Sin título"),
            size=item.get("Size", 0),
            seeders=item.get("Seeders", 0),
            leechers=item.get("Peers", 0),
            magnet=magnet,
            info_url=item.get("Details", ""),
            category=str(item.get("CategoryDesc", "")),
            indexer=item.get("Tracker", ""),
        ))

    results.sort(key=lambda r: r.seeders, reverse=True)
    return results[: config.MAX_SEARCH_RESULTS]
