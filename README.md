# Stock Watchlist Management Tool

A CLI application for tracking stock earnings dates with Discord notifications. Supports both Japanese (JP) and US markets.

## Features

- 📊 Track earnings dates for multiple stocks (JP and US markets)
- 🔔 Discord notifications for:
  - Upcoming earnings (customizable days before)
  - Significant price changes
  - Moving average crosses (golden/dead cross)
  - Pullback opportunities (bullish trend with temporary dip)
- 💾 SQLite database for data persistence
- 🌐 Multi-source data scraping (Yahoo Finance Japan, Kabutan, yfinance)
- ⏰ Cron-ready for automated checking

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set your Discord webhook URL
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

### 2. Prepare Stock List

Create a CSV file (`data/watchlist.csv`):

```csv
code,name,note
7203,トヨタ自動車,自動車メーカー
9984,ソフトバンクグループ,
AAPL,Apple,US tech stock
MSFT,Microsoft,
```

### 3. Run Initial Import and Update

```bash
# Import stocks and update data (JP market)
docker compose run --rm dev python main.py run --market jp

# For US market
docker compose run --rm dev python main.py run --market us
```

## Commands

### `run` - All-in-one Command

Import stocks from CSV, update data, and check notifications:

```bash
docker compose run --rm dev python main.py run --market jp           # JP market
docker compose run --rm dev python main.py run --market us -v        # US market, verbose
docker compose run --rm dev python main.py run stocks.csv -m jp -f   # custom CSV, force update
```

### `import` - Import Stocks from CSV

```bash
docker compose run --rm dev python main.py import                    # uses data/watchlist.csv
docker compose run --rm dev python main.py import my_stocks.csv      # custom file
```

### `update` - Update Stock Information

```bash
docker compose run --rm dev python main.py update --market jp        # update JP stocks
docker compose run --rm dev python main.py update -m us -v           # update US stocks, verbose
docker compose run --rm dev python main.py update -m jp -f           # force update (skip 6-hour cache)
```

### `check` - Check and Send Notifications

```bash
docker compose run --rm dev python main.py check --market jp         # check JP market
docker compose run --rm dev python main.py check -m us               # check US market
```

### `export` - Export Stock List to CSV

```bash
docker compose run --rm dev python main.py export                    # export to data/watchlist.csv
docker compose run --rm dev python main.py export stocks.csv         # custom file
```

### `remove` - Remove Stock from Watchlist

```bash
docker compose run --rm dev python main.py remove 7203               # remove by code
```

## Configuration

Environment variables (`.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | SQLite database path | `data/stock_watchlist.db` |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | *(required)* |
| `DEFAULT_NOTIFY_DAYS_BEFORE` | Business days before earnings to notify | `2` |
| `PRICE_CHANGE_THRESHOLD` | Price change threshold (%) for alerts | `5.0` |

## Cron Setup

Schedule automatic checks using cron:

```bash
# JP market - weekdays at 16:00 JST (after market close)
0 16 * * Mon-Fri cd /docker/cli && docker compose run --rm stock-watchlist run -m jp

# US market - Tue-Sat at 08:00 JST (after US market close)
0 8 * * Tue-Sat cd /docker/cli && docker compose run --rm stock-watchlist run -m us
```

## Discord Notifications

All notifications display:
- Stock name and code (with link to chart)
- Current price with change percentage
- PER (Price-to-Earnings Ratio)
- Dividend yield (%)

### 1. Earnings Notifications
Color-coded by urgency:
- 🔴 Red: Earnings today
- 🟠 Orange: Earnings tomorrow
- 🟡 Yellow: Earnings in 2+ days

### 2. Price Change Notifications
- 📈 Green: Positive change
- 📉 Red: Negative change
- Triggered when change exceeds threshold (default: 5%)

### 3. MA Cross Notifications
- 🌟 Golden Cross: MA25 crossed above MA75 (bullish signal)
- ⚠️ Dead Cross: MA25 crossed below MA75 (bearish signal)

### 4. Pullback Opportunity Notifications
- 🎯 Cyan: MA25 > MA75 but price < MA75
- Indicates potential buying opportunity in uptrend

## Market Detection

Markets are automatically detected from stock codes:
- **JP stocks**: 4-digit codes starting with number (e.g., `7203`, `9984`)
- **US stocks**: Other codes (e.g., `AAPL`, `MSFT`, `GOOGL`)

## Data Sources

- **JP stocks**: Yahoo Finance Japan, Kabutan, yfinance
- **US stocks**: yfinance API
- API calls are cached for 6 hours to avoid rate limiting

## Project Structure

```
stock_watchlist/
├── compose.yaml           # Docker Compose configuration
├── .env                   # Environment variables
├── .env.example           # Environment template
├── README.md              # This file
└── app/
    ├── main.py            # CLI entry point
    ├── database.py        # Database operations
    ├── stock_api.py       # Stock data fetching
    ├── notifier.py        # Discord notifications
    ├── config.py          # Configuration
    └── data/
        └── stock_watchlist.db  # SQLite database
```

## License

This project is for personal use.
