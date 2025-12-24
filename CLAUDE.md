# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stock Watchlist Management Tool - CLI app for tracking stock earnings dates with Discord notifications. Supports JP and US markets. Uses SQLite for persistence, scrapes data from Yahoo Finance (yfinance) and Kabutan.jp.

## Common Commands

**IMPORTANT**: Always use Docker Compose to run Python commands:
```bash
docker compose run --rm dev python main.py [command]
```

| Command | Description |
|---------|-------------|
| `run --market jp` | Import CSV + update JP stocks + check notifications |
| `run --market us -v` | Import CSV + update US stocks (verbose) |
| `run --market jp -k` | Same as above + refresh Kabutan data |
| `update --market jp` | Update JP stocks only (no import) |
| `import [file.csv]` | Import stocks from CSV (default: data/watchlist.csv) |
| `export [file.csv]` | Export stocks to CSV |
| `check` | Check upcoming earnings and send notifications |

- Config: `cp .env.example .env` (Docker Compose config: `compose.yaml`)
- Cron example: `0 16 * * Mon-Fri cd /docker/cli && docker compose run --rm stock-watchlist run -m jp`

## Architecture

### Project Structure
```
stock_watchlist/
├── compose.yaml / Dockerfile / Dockerfile.dev
├── .env / .env.example
└── app/
    ├── main.py         # CLI entry point (Click framework)
    ├── database.py     # SQLite operations
    ├── stock_api.py    # yfinance data fetching
    ├── kabutan_api.py  # Kabutan.jp scraping (JP only)
    ├── notifier.py     # Discord webhook notifications
    ├── config.py       # Environment-based configuration
    └── data/stock_watchlist.db
```

### Data Flow

1. **`run` command**: `_do_import()` → `_do_update_all()` → `_do_check()`
2. **`update` command** (requires `--market jp|us`):
   1. yfinance: fetch price, prev_price, earnings_date + 1yr price history
   2. `database.save_price_history_bulk()` → `price_history` table
   3. `database.calculate_moving_averages()` → MA25/MA75 (date-based)
   4. `database.calculate_price_breakouts()` → 30/90/180/360-day breakouts
   5. Kabutan (JP only): fetch EPS, dividend (if null or `--kabutan` flag)
   6. `database.update_stock()` saves all data
3. **`check` command**: queries and sends 5 notification types via Discord

### Database Schema

**watchlist**: `code` (PK), `name`, `market`, `earnings_date`, `price`, `prev_price`, `price_change_rate`, `dividend`, `dividend_yield`, `eps`, `per`, `ma25`, `ma75`, `prev_ma25`, `prev_ma75`, `high_breakout`, `low_breakout`, `note`

**price_history**: `stock_code` (FK), `date` (YYYY-MM-DD), `close` — PK: (`stock_code`, `date`)

**Market auto-detection**: 4-digit code starting with number = `jp` (7203, 9984); otherwise = `us` (AAPL, MSFT)

**Breakout fields**: Store longest period (30/90/180/360 days) where price exceeds historical high/low. NULL if no breakout.

### Configuration

Env vars via `os.getenv()` in `config.py` (no auto-loading):
- `DB_PATH`: default `data/stock_watchlist.db`
- `DISCORD_WEBHOOK_URL`: required for notifications
- `DEFAULT_NOTIFY_DAYS_BEFORE`: default 2 (business days)
- `PRICE_CHANGE_THRESHOLD`: default 5.0 (%)

### Data Sources

| Source | JP stocks | US stocks |
|--------|-----------|-----------|
| yfinance | price, prev_price, earnings_date, price history | + EPS, dividend |
| Kabutan.jp | EPS (修正1株益), dividend (修正1株配) — when null or `-k` flag | not used |

- **JP ticker**: `.T` suffix added automatically (7203 → 7203.T)
- **PER**: Always calculated as `price ÷ EPS` in `main.py` (never from yfinance)
- **MA25/MA75**: Calculated from `price_history` table, not yfinance directly
  - `database.calculate_moving_averages()`: latest 76 records, simple moving average
  - `prev_ma25`/`prev_ma75` saved before update (used for cross detection)
- **Kabutan scraping**: Prioritizes "予" (forecast) over actual; skips comparison rows; 0.5s rate limit

### Discord Notifications (5 types)

| Type | Trigger | Color/Icon |
|------|---------|------------|
| Earnings | within N business days | Red/Orange/Yellow by urgency |
| Price change | `abs(price_change_rate) >= threshold` | — |
| MA cross | Golden (MA25↑MA75) / Dead (MA25↓MA75) | — |
| Pullback | MA25>MA75 && price<MA75 | Cyan 🎯 |
| Breakout | high/low_breakout IS NOT NULL | Green 🚀 / Red 📉 / Gold ⚡ |

- All show: price with change %, PER, dividend yield (when available)
- MA values, EPS, dividend amounts not shown in notifications
- Multiple stocks batched into single webhook (max 10 embeds per call)
- Breakouts sorted by period (longest first)

## Development Notes

### Database Migrations

**IMPORTANT**: Do NOT create migration code. To change schema:
1. Update `_init_database()` in `database.py`
2. Delete `data/stock_watchlist.db`
3. Run any command to auto-recreate

### CLI Guidelines

- Click framework; `@cli.command()` decorator in `app/main.py`
- Use `click.echo()` for output (except `_do_check()` uses `print()` for cron logging)
- Error messages: `click.echo(..., err=True)`
- `run`/`update` require `--market jp|us`
- Market stored at import time; not in CSV files
- `add_stock()` only stores basic info (code, name, market, note); data fields init to NULL

### CSV Format

```csv
code,name,note
7203,トヨタ自動車,自動車メーカー
AAPL,Apple,US tech stock
```
- `market` is NOT in CSV — auto-detected from code at import time

### Adding New Data Sources

1. Implement method in `stock_api.py`, return `YYYY-MM-DD` or `None`
2. Add to `sources` list in `get_earnings_date()`
3. Add `time.sleep()` for rate limiting

### Adding New Notification Types

1. `database.py`: add `get_stocks_with_<condition>()` query method
2. `notifier.py`: add `send_<type>_notification()` with embeds (handle 10-embed chunking)
3. `app/main.py` → `_do_check()`: call query + send
4. Update this CLAUDE.md (Data Flow + Discord Notifications sections)
