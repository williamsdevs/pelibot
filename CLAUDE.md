# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

PeliBot is a Telegram bot written in Python that allows authorized users to search for movies and series via **Jackett** (a universal torrent indexer proxy) and download them through **qBittorrent**'s Web API. TMDB is optionally used for movie metadata and posters.

## Running the bot

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Run
python main.py
```

## Environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `ALLOWED_USER_IDS` | No | Comma-separated Telegram user IDs; empty = allow all |
| `QB_HOST` / `QB_PORT` | Yes | qBittorrent WebUI address |
| `QB_USERNAME` / `QB_PASSWORD` | Yes | qBittorrent credentials |
| `QB_DOWNLOAD_PATH` | No | Default save path for torrents |
| `JACKETT_URL` | Yes | Jackett base URL |
| `JACKETT_API_KEY` | Yes | Found in Jackett dashboard |
| `TMDB_API_KEY` | No | Enables poster images; leave empty to disable |

## Architecture

```
main.py                  — Entry point: wires handlers, runs polling loop
config.py                — Reads all env vars; import this everywhere for config
bot/
  handlers/
    auth.py              — @restricted decorator for user allowlist
    general.py           — /start, /ayuda
    search.py            — /buscar flow: search → select → confirm → download
    status.py            — /estado: lists active qBittorrent downloads
  keyboards.py           — InlineKeyboardMarkup builders
services/
  jackett.py             — Async Jackett API client; returns List[TorrentResult]
  qbittorrent.py         — Async qBittorrent Web API client
  tmdb.py                — Optional TMDB metadata/poster lookup
```

### Search flow

1. `/buscar <query>` → `search.cmd_buscar` calls `jackett.search()` and `tmdb.search_movie()` in parallel
2. Results stored in `context.user_data["search_results"]`; user sees inline keyboard
3. Tapping a result → `callback_torrent_selected` shows confirmation with torrent details
4. Confirming → `callback_confirm` calls `qbittorrent.add_magnet()`

## Adding new commands

1. Create handler function in `bot/handlers/` decorated with `@restricted`
2. Register it in `main.py` with `app.add_handler(CommandHandler(...))`

## Adding new torrent indexers / future Arr integration

- Replace or extend `services/jackett.py` — the rest of the codebase only imports `TorrentResult` and `jackett.search()`
- To integrate Sonarr/Radarr, add a `services/sonarr.py` / `services/radarr.py` and call their APIs instead of (or in addition to) `qbittorrent.add_magnet()`
