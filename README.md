# Stock Watchlist Management Tool

CLI app for tracking stock earnings dates with Discord notifications. Supports JP and US markets.

## Setup

```bash
cp .env.example .env
# Set DISCORD_WEBHOOK_URL
```

## Quick Start

```bash
# JP market: import CSV → update data → check notifications
docker compose run --rm dev python main.py run --market jp

# US market
docker compose run --rm dev python main.py run --market us
```

`data/watchlist.csv` format:

```csv
code,name,note
7203,トヨタ自動車,
AAPL,Apple,
```

Market is auto-detected from stock code (4-digit number = JP, otherwise = US).

---

For commands, configuration, architecture, and development guide, see [CLAUDE.md](./CLAUDE.md).
