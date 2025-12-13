# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stock Watchlist Management Tool - A CLI application for tracking stock earnings dates with Discord notifications. Supports both Japanese (JP) and US markets. Uses SQLite for data persistence and scrapes earnings data from multiple sources (Yahoo Finance Japan, Kabutan, yfinance).

## Common Commands

### Running the Application
**IMPORTANT**: Always use Docker Compose to run Python commands:
```bash
# Run CLI commands from project root via Docker Compose
docker compose run --rm dev python main.py [command]

# Import stocks from CSV, update all data, and check notifications (all-in-one)
docker compose run --rm dev python main.py run --market jp                    # uses data/watchlist.csv, update JP stocks
docker compose run --rm dev python main.py run --market us -v                 # update US stocks with verbose output
docker compose run --rm dev python main.py run my_stocks.csv --market jp -v   # custom CSV file
docker compose run --rm dev python main.py run --market jp -k                 # update JP stocks and refresh Kabutan data

# Update all watchlist stocks (market required)
docker compose run --rm dev python main.py update --market jp        # update JP stocks only
docker compose run --rm dev python main.py update --market us -v     # update US stocks with verbose output
docker compose run --rm dev python main.py update --market jp -k     # update JP stocks and refresh Kabutan data

# Import/export stock lists
docker compose run --rm dev python main.py import                 # import from data/watchlist.csv
docker compose run --rm dev python main.py import stocks.csv      # import from custom CSV
docker compose run --rm dev python main.py export                 # export to data/watchlist.csv
docker compose run --rm dev python main.py export stocks.csv      # export to custom CSV

# Check for upcoming earnings and send notifications (designed for cron)
docker compose run --rm dev python main.py check
```

### Setup and Configuration
```bash
# Configure environment variables (copy and edit .env.example)
cp .env.example .env
```

**Note**: The Docker Compose configuration file is `compose.yaml` at the project root.

### Cron Setup
The `check` command is designed to be run via cron for periodic execution:
```bash
# Example: Check daily at 9:00 AM using Docker Compose
0 16 * * Mon-Fri cd /docker/cli && docker compose run --rm stock-watchlist run -m jp
0  8 * * Tue-Sat cd /docker/cli && docker compose run --rm stock-watchlist run -m us
```

## Architecture

### Project Structure
```
stock_watchlist/
├── compose.yaml           # Docker Compose configuration
├── .dockerignore          # Docker build exclusions
├── Dockerfile             # Production Docker image
├── Dockerfile.dev         # Development Docker image
├── .env                   # Environment variables (not in git)
├── .env.example           # Environment variables template
├── README.md              # Project documentation
├── CLAUDE.md              # AI assistant instructions
└── app/
    ├── main.py            # CLI entry point and commands (Click framework)
    ├── database.py        # SQLite operations
    ├── stock_api.py       # Stock data fetching from yfinance
    ├── kabutan_api.py     # Stock data scraping from Kabutan.jp (JP stocks only)
    ├── notifier.py        # Discord webhook notifications
    ├── config.py          # Environment-based configuration
    ├── requirements.txt   # Python dependencies
    ├── entrypoint.sh      # Docker entrypoint script
    └── data/
        └── stock_watchlist.db # SQLite database (auto-created)
```

### Data Flow

1. **Stock Import/Update Flow (`run` command)**:
   - Step 1: `_do_import()` reads CSV file, adds new stocks or updates name/note for existing stocks
     - Market is auto-detected from stock code: 4-digit starting with number = jp, else = us
   - Step 2: `_do_update_all(verbose, market, update_kabutan)` updates stocks in specified market
     - **Important**: Requires `--market` option (jp or us)
     - **JP market**: EPS/dividend fetched from Kabutan if null or if `--kabutan` flag is used
     - **US market**: EPS/dividend always fetched from yfinance
   - Step 3: `_do_check()` checks for upcoming earnings and sends notifications

2. **Manual Update Flow (`update` command)**:
   - **Important**: Requires `--market` option (jp or us) to specify which market to update
   - **Data Sources**:
     - **JP stocks**: Price/MA from yfinance, EPS/dividend from Kabutan (only if null or `--kabutan` flag)
     - **US stocks**: Price/MA/EPS/dividend all from yfinance
   - `stock_api.StockAPI` fetches price, prev_price, MA25, MA75, earnings_date from yfinance
   - `kabutan_api.KabutanAPI` fetches revised EPS and dividend from Kabutan.jp (JP stocks only)
   - `database.Database` updates stock data

3. **Notification Flow (`check` command)**:
   - `check` command runs (triggered by cron or manually)
   - Checks four types of events:
     - **Earnings dates**: Queries stocks with earnings within notification window (default: 2 business days)
     - **Price changes**: Queries stocks with price changes exceeding threshold (default: 5%)
     - **MA crosses**: Detects golden cross (MA25 > MA75) or dead cross (MA25 < MA75)
     - **Pullback opportunities**: Detects MA25 > MA75 && price < MA75 (bullish trend with temporary pullback)
   - `notifier.DiscordNotifier` sends rich embeds via webhook

### Database Schema

**watchlist table**:
- Stores stock information with price data, dividend yield, PER metrics, and earnings dates
- Key fields: `code` (unique), `name`, `market`, `earnings_date`, `price`, `prev_price`, `price_change_rate`, `dividend`, `dividend_yield`, `eps`, `per`, `ma25`, `ma75`, `prev_ma25`, `prev_ma75`, `note`
- Note: `dividend`, `eps`, and MA fields are stored in database but not displayed in Discord notifications
- **Market field**: Stores market type (`jp` or `us`), auto-detected from stock code during import
  - 4-digit code starting with number = `jp` (e.g., 7203, 9984)
  - Other codes = `us` (e.g., AAPL, MSFT)
- **MA fields**: `prev_ma25` and `prev_ma75` are automatically saved before updating MA values (used for cross detection)

### Configuration Management

Environment variables are read directly via `os.getenv()` in `config.py` (no .env file auto-loading):
- `DB_PATH`: SQLite database location (default: `data/stock_watchlist.db`)
- `DISCORD_WEBHOOK_URL`: Discord webhook URL (required for notifications)
- `DEFAULT_NOTIFY_DAYS_BEFORE`: Business days before earnings to notify (default: 2)
- `PRICE_CHANGE_THRESHOLD`: Price change threshold percentage for notifications (default: 5.0)

Set environment variables in your shell or use a process manager. The `.env.example` file shows required variables.

### Stock Data Scraping

The application uses two separate APIs for different data:

#### 1. **yfinance API (`stock_api.StockAPI`)**:
   - **Data retrieved**: price, prev_price, ma25, ma75, prev_ma25, prev_ma75, earnings_date
   - **US stocks only**: Also retrieves eps (trailingEps/forwardEps) and dividend (dividendRate/lastDividend)
   - **Earnings date**: Fetched from `stock.calendar` API
   - **JP stocks**: `.T` suffix automatically added for Yahoo Finance API calls (e.g., "7203" → "7203.T")
   - **US stocks**: Ticker symbols used directly (e.g., "AAPL", "MSFT")

#### 2. **Kabutan API (`kabutan_api.KabutanAPI`)** - JP stocks only:
   - **Data retrieved**: eps (修正1株益), dividend (修正1株配)
   - **Scraping strategy**:
     - Prioritizes company forecast values ("予") over actual results
     - Falls back to actual results if forecast is "－" (undefined)
     - Skips comparison rows ("前期比", "前年同期比", "同期比")
   - **When used**:
     - Automatically when EPS is null in database (for JP market)
     - Manually with `--kabutan` flag to refresh data
   - **Rate limiting**: 0.5s delay between requests
   - **User-Agent**: Included to prevent bot blocking

#### 3. **PER Calculation**:
   - Always calculated in `main.py` as `PER = price ÷ EPS` when both values are available
   - Never uses yfinance's pre-calculated PER values

**Key Implementation Details**:
- **JP stocks**: Price/MA from yfinance, EPS/dividend from Kabutan
- **US stocks**: All data from yfinance
- Only future dates are considered valid earnings dates
- MA values are calculated using pandas rolling window (25-day and 75-day)

### Discord Notifications

The `notifier.DiscordNotifier` sends rich embed messages for four notification types:

1. **Earnings Notifications**:
   - Color-coded urgency: Red (today), Orange (tomorrow), Yellow (2+ days)
   - Displays: Earnings date, stock price with change percentage, PER, dividend yield

2. **Price Change Notifications**:
   - Triggered when `abs(price_change_rate) >= PRICE_CHANGE_THRESHOLD`
   - Displays: Current price with change percentage, PER, dividend yield

3. **MA Cross Notifications**:
   - Golden cross (MA25 crosses above MA75): Bullish signal
   - Dead cross (MA25 crosses below MA75): Bearish signal
   - Detects crosses by comparing current and previous MA values
   - Displays: Signal type, current price with change percentage, PER, dividend yield

4. **Pullback Opportunity Notifications**:
   - Triggered when MA25 > MA75 && price < MA75
   - Indicates a potential buying opportunity (bullish trend with temporary price pullback)
   - Cyan color (🎯 icon) for visual identification
   - Displays: Signal type, current price with change percentage, PER, dividend yield

**Implementation details**:
- Multiple stocks batched into single webhook call with multiple embeds
- All notifications show PER and dividend yield (%) when available
- MA values, EPS, and dividend amounts are not displayed in notifications

## Development Notes

### Adding New Stock Data Sources

To add a new earnings date source:
1. Implement scraper method in `stock_api.py` (e.g., `get_earnings_date_from_newsite()`)
2. Add to `sources` list in `get_earnings_date()` method
3. Return `YYYY-MM-DD` format string or `None`
4. Handle rate limiting with `time.sleep()` between attempts

### Database Migrations

SQLite schema auto-initializes on first run. To add columns:
1. Update table creation in `database.py` → `_init_database()`
2. Add migration logic to handle existing databases if needed
3. Update relevant CRUD methods (`add_stock`, `update_stock`, etc.)

**Recent migrations**:
- `prev_ma25`, `prev_ma75`: Added for MA cross detection
- `market`: Added to store market type (jp/us)
- `added_date`, `last_updated`, `last_api_call`: Removed (no longer needed)

### CLI Command Structure

All CLI commands use Click framework:
- Defined in `app/main.py` with `@cli.command()` decorator
- Database/API instances created at module level for reuse
- Use `click.echo()` for user output, not `print()` (except in `_do_check()` which uses `print()` for cron logging)
- Error messages should use `err=True` parameter

**Important implementation notes**:
- Both `run` and `update` commands require `--market` option (jp or us) to specify which market to update
- `--kabutan/-k` option: Forces refresh of EPS and dividend from Kabutan even if already exists (JP market only)
- `_do_import()` auto-detects market from stock code: 4-digit starting with number = jp, else = us
- Market detection happens at import time and is stored in the `market` field
- Business days (Monday-Friday) are used for earnings notification window calculations via `_count_business_days()`
- PER and dividend_yield are calculated in main.py using database values, not fetched from APIs

### CSV Import/Export Format

CSV files should have the following columns:
- `code` (required): Stock code (e.g., 7203, AAPL)
- `name` (optional): Stock name
- `note` (optional): User notes/remarks

**Important**: The `market` field is NOT included in CSV files. It is automatically detected during import:
- 4-digit code starting with number → `jp` (e.g., 7203, 9984)
- Other codes → `us` (e.g., AAPL, MSFT, GOOGL)

Example CSV:
```csv
code,name,note
7203,トヨタ自動車,自動車メーカー
9984,ソフトバンクグループ,
AAPL,Apple,US tech stock
MSFT,,
```

### Adding New Notification Types

To add a new notification type:

1. **Add database query method** in `database.py`:
   ```python
   def get_stocks_with_new_condition(self) -> List[dict]:
       """Query stocks matching the new condition"""
       # Implement SQL query
       pass
   ```

2. **Add notification method** in `notifier.py`:
   ```python
   def send_new_notification(self, stocks: List[Dict]) -> bool:
       """Send new notification type to Discord"""
       # Create embeds with color, emoji, and fields
       # Handle chunking for Discord's 10 embed limit
       pass
   ```

3. **Update check command** in `app/main.py` → `_do_check()`:
   - Query stocks with new condition
   - Send notification

4. **Update documentation**:
   - Add notification type to CLAUDE.md (Data Flow, Discord Notifications sections)
   - Update `check` command docstring

Example: The pullback opportunity notification (MA25 > MA75 && price < MA75) was implemented following these steps:
- `database.py` - `get_stocks_with_pullback_opportunity()`
- `notifier.py` - `send_pullback_notification()`
- `app/main.py` - Check and send logic
