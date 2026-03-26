"""AI-powered torrent selection using Groq."""
import json
import logging

import config

logger = logging.getLogger(__name__)


async def pick_best_torrent(query: str, results: list) -> tuple[int, str]:
    """
    Ask Groq to pick the best torrent from a list of results.
    Returns (index, reasoning) — index into results list.
    Falls back to index 0 (most seeded) if AI fails.
    """
    if not config.GROQ_API_KEY or not results:
        return 0, "Sin IA configurada, se eligió el más sembrado."

    # Build a compact summary of each result
    options = []
    for i, r in enumerate(results):
        options.append({
            "index": i,
            "title": r.title,
            "size": r.size_gb,
            "seeds": r.seeders,
            "peers": r.leechers,
            "indexer": r.indexer,
        })

    prompt = f"""Eres un experto en torrents. El usuario busca: "{query}"

Aquí están los resultados disponibles:
{json.dumps(options, ensure_ascii=False, indent=2)}

Elige el MEJOR torrent considerando:
1. Que el título coincida bien con lo que busca el usuario
2. Cantidad de seeds (más = mejor y más rápido)
3. Tamaño razonable (no demasiado pequeño ni exageradamente grande)
4. Evitar CAM, TS, HDCAM o copias de baja calidad
5. Preferir 1080p sobre 720p si el tamaño es razonable

Responde SOLO con un JSON así (sin texto adicional):
{{"index": 0, "reason": "Explicación breve en español"}}"""

    try:
        from groq import Groq
        import asyncio

        client = Groq(api_key=config.GROQ_API_KEY)

        def _call():
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()

        raw = await asyncio.get_event_loop().run_in_executor(None, _call)

        # Parse JSON response
        # Strip markdown code blocks if present
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        index = int(data.get("index", 0))
        reason = data.get("reason", "")

        # Validate index
        if index < 0 or index >= len(results):
            index = 0

        return index, reason

    except Exception as exc:
        logger.error("Groq AI error: %s", exc)
        return 0, "IA no disponible, se eligió el más sembrado."
