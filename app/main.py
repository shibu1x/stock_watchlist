#!/usr/bin/env python3
"""Japanese Stock Watchlist Management Tool - Main Program"""
import click
import csv
from pathlib import Path
from database import Database
from stock_api import StockAPI
from kabutan_api import KabutanAPI
from notifier import DiscordNotifier
from config import Config
from datetime import datetime, timedelta


# Database instances
db = Database()
stock_api = StockAPI()
kabutan_api = KabutanAPI()
notifier = DiscordNotifier()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Japanese Stock Watchlist Management Tool

    Manage earnings dates for watchlist stocks and send notifications.
    """
    pass


# Helper functions
def _count_business_days(start_date, end_date):
    """Count business days between two dates (excluding weekends)

    Args:
        start_date: Start date (datetime object)
        end_date: End date (datetime object)

    Returns:
        Number of business days (Monday-Friday) between start and end dates
    """
    business_days = 0
    current = start_date.date() if isinstance(start_date, datetime) else start_date
    target = end_date.date() if isinstance(end_date, datetime) else end_date

    while current < target:
        # weekday(): Monday=0, Sunday=6
        if current.weekday() < 5:  # Monday to Friday
            business_days += 1
        current += timedelta(days=1)

    return business_days
def _do_import(input_file):
    """Import stocks from CSV file and return summary"""
    input_path = Path(input_file).resolve()

    with open(input_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        if 'code' not in reader.fieldnames:
            click.echo("Error: CSV file must have 'code' column", err=True)
            return None

        stocks_to_add = []
        for row in reader:
            code = row.get('code', '').strip()
            if code:
                name = row.get('name', '').strip() or None
                note = row.get('note', '').strip() or None
                # Auto-detect market: 4-digit code starting with number = jp, else = us
                if len(code) == 4 and code[0].isdigit():
                    market = 'jp'
                else:
                    market = 'us'
                stocks_to_add.append({'code': code, 'name': name, 'market': market, 'note': note})

    if not stocks_to_add:
        click.echo("Error: No valid stock codes found in file", err=True)
        return None

    click.echo(f"Found {len(stocks_to_add)} stocks in file: {input_path}\n")

    total_stocks = len(stocks_to_add)
    added_count = 0
    updated_count = 0
    failed_count = 0

    for idx, stock_data in enumerate(stocks_to_add, 1):
        code = stock_data['code']
        name = stock_data['name']
        market = stock_data['market']
        note = stock_data['note']

        existing_stock = db.get_stock(code)
        if existing_stock:
            if name or note:
                success = db.update_stock(code, name=name, market=market, note=note)
                if success:
                    updates = []
                    if name:
                        updates.append("name")
                    if note:
                        updates.append("note")
                    update_msg = f"Updated {', '.join(updates)}" if updates else "No updates"
                    display_name = name or existing_stock.get('name') or code
                    click.echo(f"[{idx}/{total_stocks}] {code} ({display_name}): {update_msg}")
                    updated_count += 1
                else:
                    click.echo(f"[{idx}/{total_stocks}] {code}: Failed to update")
                    failed_count += 1
            else:
                # Always update market silently when stock already exists
                db.update_stock(code, market=market)
                existing_name = existing_stock.get('name') or code
                click.echo(f"[{idx}/{total_stocks}] {code} ({existing_name}): Already registered (no updates)")
                updated_count += 1
        else:
            success = db.add_stock(code, name, market=market, note=note)
            if success:
                display_name = f" ({name})" if name else ""
                click.echo(f"[{idx}/{total_stocks}] {code}{display_name}: Added")
                added_count += 1
            else:
                click.echo(f"[{idx}/{total_stocks}] {code}: Failed to add")
                failed_count += 1

    click.echo("\n" + "=" * 60)
    summary_parts = []
    if added_count > 0:
        summary_parts.append(f"{added_count} added")
    if updated_count > 0:
        summary_parts.append(f"{updated_count} updated")
    if failed_count > 0:
        summary_parts.append(f"{failed_count} failed")
    click.echo(f"Summary: {', '.join(summary_parts)} out of {total_stocks} stocks")
    click.echo("=" * 60)

    return {'added': added_count, 'updated': updated_count, 'failed': failed_count, 'total': total_stocks}


def _do_update_all(verbose=False, market='jp', update_kabutan=False):
    """Update all stocks and return summary

    Args:
        verbose: Show detailed information
        market: Market to filter (jp or us). Defaults to 'jp'.
        update_kabutan: Update EPS and dividend from Kabutan even if already exists
    """
    stocks = db.get_all_stocks()

    if not stocks:
        click.echo("No watchlist stocks registered")
        return None

    # Filter by market if specified
    if market:
        stocks = [s for s in stocks if s.get('market') == market]
        if not stocks:
            click.echo(f"No stocks found for market: {market}")
            return None

    total_stocks = len(stocks)
    success_count = 0
    failed_count = 0

    market_msg = f" ({market.upper()} market)" if market else ""
    click.echo(f"Updating {total_stocks} stocks{market_msg}...\n")

    for idx, stock in enumerate(stocks, 1):
        code = stock['code']

        click.echo(f"[{idx}/{total_stocks}] Updating stock: {code}")
        click.echo("-" * 60)

        # If EPS is null or update_kabutan is True, fetch from Kabutan first (JP market only)
        eps = stock.get('eps')
        dividend = stock.get('dividend')

        if (eps is None or update_kabutan) and market == 'jp':
            click.echo("Fetching EPS and dividend from Kabutan...")
            kabutan_info = kabutan_api.get_stock_info(code, verbose=verbose)
            if kabutan_info:
                eps = kabutan_info.get('eps')
                dividend = kabutan_info.get('dividend')
                if verbose:
                    if eps is not None:
                        click.echo(f"EPS (Revised): ¥{eps:,.2f}")
                    if dividend is not None:
                        click.echo(f"Dividend (Revised): ¥{dividend:,.2f}")

        # Fetch stock information
        click.echo("Fetching stock information...")
        info = stock_api.get_stock_info(code)

        if not info:
            click.echo(f"Error: Could not fetch information for stock {code}", err=True)
            failed_count += 1
            continue

        # Use existing name from database
        display_name = stock.get('name') or code

        price = info.get('price')
        prev_price = info.get('prev_price')
        ma25 = info.get('ma25')
        ma75 = info.get('ma75')
        prev_ma25 = info.get('prev_ma25')
        prev_ma75 = info.get('prev_ma75')
        earnings_date = info.get('earnings_date')

        # Use yfinance EPS and dividend for US market
        if market == 'us':
            eps = info.get('eps')
            dividend = info.get('dividend')

        price_change_rate = None
        if price and prev_price and prev_price > 0:
            price_change_rate = ((price - prev_price) / prev_price) * 100

        # Calculate PER from EPS
        per = None
        if price and eps and eps > 0:
            per = price / eps

        # Calculate dividend yield from dividend
        dividend_yield = None
        if price and dividend and price > 0:
            dividend_yield = (dividend / price) * 100

        click.echo(f"Stock name: {display_name}")
        if price:
            click.echo(f"Current price: ¥{price:,.0f}")
            if price_change_rate is not None:
                click.echo(f"Change: {price_change_rate:+.2f}%")

        if verbose:
            if ma25:
                click.echo(f"25-day MA: ¥{ma25:,.2f}")
            if ma75:
                click.echo(f"75-day MA: ¥{ma75:,.2f}")
            if per:
                click.echo(f"PER (calculated): {per:.2f}")
            if dividend_yield:
                click.echo(f"Dividend yield (calculated): {dividend_yield:.2f}%")

        # Update stock
        success = db.update_stock(code, earnings_date=earnings_date,
                                 price=price, prev_price=prev_price, price_change_rate=price_change_rate,
                                 eps=eps, dividend=dividend, per=per, dividend_yield=dividend_yield,
                                 ma25=ma25, ma75=ma75, prev_ma25=prev_ma25, prev_ma75=prev_ma75)
        if success:
            click.echo(f"✓ Stock updated: {display_name}")
            success_count += 1
        else:
            click.echo(f"Error: Failed to update stock", err=True)
            failed_count += 1

        click.echo("")

    click.echo("=" * 60)
    click.echo(f"Summary: {success_count} succeeded, {failed_count} failed out of {total_stocks} stocks")
    click.echo("=" * 60)

    return {'success': success_count, 'failed': failed_count, 'total': total_stocks}


def _do_check(market='jp'):
    """Check for upcoming earnings, price changes, MA crosses, and pullback opportunities, then send notifications

    Args:
        market: Market to filter (jp or us). Defaults to 'jp'.
    """
    market_msg = f" ({market.upper()} market)" if market else ""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking earnings dates, price changes, MA crosses, and pullback opportunities{market_msg}...")

    # Check earnings dates
    notify_days_before = Config.DEFAULT_NOTIFY_DAYS_BEFORE
    earnings_stocks_to_notify = []
    all_stocks = db.get_all_stocks()

    # Filter by market if specified
    if market:
        all_stocks = [s for s in all_stocks if s.get('market') == market]

    for stock in all_stocks:
        earnings_date = stock.get('earnings_date')
        if not earnings_date:
            continue

        try:
            earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

            # Count business days (excluding weekends) until earnings date
            business_days_until = _count_business_days(datetime.now(), earnings_dt)

            # Notify if within the business days threshold
            if 0 <= business_days_until <= notify_days_before:
                earnings_stocks_to_notify.append(stock)

        except ValueError:
            print(f"Warning: Invalid earnings date format: {earnings_date} ({stock.get('code')})")
            continue

    # Send earnings notifications
    earnings_notified = 0
    if earnings_stocks_to_notify:
        print(f"Earnings notification targets: {len(earnings_stocks_to_notify)} stocks")

        success = notifier.send_earnings_notification(earnings_stocks_to_notify)

        if success:
            print("Earnings notification completed")
            earnings_notified = len(earnings_stocks_to_notify)
        else:
            print("Error: Failed to send earnings notification")
    else:
        print("No earnings notifications to send")

    # Check price changes
    price_change_threshold = Config.PRICE_CHANGE_THRESHOLD
    price_change_stocks = db.get_stocks_with_price_change(threshold=price_change_threshold, market=market)

    # Send price change notifications
    price_notified = 0
    if price_change_stocks:
        print(f"Price change notification targets: {len(price_change_stocks)} stocks (threshold: {price_change_threshold}%)")

        success = notifier.send_price_change_notification(price_change_stocks)

        if success:
            print("Price change notification completed")
            price_notified = len(price_change_stocks)
        else:
            print("Error: Failed to send price change notification")
    else:
        print("No price change notifications to send")

    # Check MA crosses
    ma_cross_stocks = db.get_stocks_with_ma_cross(market=market)

    # Send MA cross notifications
    ma_cross_notified = 0
    if ma_cross_stocks:
        golden_count = sum(1 for s in ma_cross_stocks if s.get('cross_type') == 'golden')
        dead_count = sum(1 for s in ma_cross_stocks if s.get('cross_type') == 'dead')
        print(f"MA cross notification targets: {len(ma_cross_stocks)} stocks (golden: {golden_count}, dead: {dead_count})")

        success = notifier.send_ma_cross_notification(ma_cross_stocks)

        if success:
            print("MA cross notification completed")
            ma_cross_notified = len(ma_cross_stocks)
        else:
            print("Error: Failed to send MA cross notification")
    else:
        print("No MA cross notifications to send")

    # Check pullback opportunities (MA25 > MA75 && price < MA75)
    pullback_stocks = db.get_stocks_with_pullback_opportunity(market=market)

    # Send pullback opportunity notifications
    pullback_notified = 0
    if pullback_stocks:
        print(f"Pullback opportunity notification targets: {len(pullback_stocks)} stocks")

        success = notifier.send_pullback_notification(pullback_stocks)

        if success:
            print("Pullback opportunity notification completed")
            pullback_notified = len(pullback_stocks)
        else:
            print("Error: Failed to send pullback opportunity notification")
    else:
        print("No pullback opportunity notifications to send")

    total_notified = earnings_notified + price_notified + ma_cross_notified + pullback_notified
    print(f"Total notifications sent: {total_notified} (earnings: {earnings_notified}, price change: {price_notified}, MA cross: {ma_cross_notified}, pullback: {pullback_notified})")

    return total_notified


@cli.command()
@click.argument('code')
def remove(code):
    """Remove watchlist stock

    Examples:
      python main.py remove 7203
    """
    stock = db.get_stock(code)
    if not stock:
        click.echo(f"Error: Stock {code} is not registered", err=True)
        return

    success = db.remove_stock(code)
    if success:
        stock_name = stock.get('name') or code
        click.echo(f"✓ Stock removed: {stock_name}")
    else:
        click.echo(f"Error: Failed to remove stock", err=True)


@cli.command()
@click.option('--market', '-m', type=click.Choice(['jp', 'us']), default='jp', help='Market to update (jp or us). Defaults to jp.')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--kabutan', '-k', is_flag=True, help='Update EPS and dividend from Kabutan even if already exists (JP only)')
def update(market, verbose, kabutan):
    """Update information for watchlist stocks in specified market

    Fetches latest stock information and earnings dates for registered stocks in the specified market.

    Examples:
      python main.py update                    # update JP stocks (default)
      python main.py update --market jp        # update JP stocks
      python main.py update -m us -v           # update US stocks with verbose output
      python main.py update -k                 # update JP stocks and refresh Kabutan data
    """
    click.echo("")
    _do_update_all(verbose, market, update_kabutan=kabutan)


@cli.command()
@click.option('--market', '-m', type=click.Choice(['jp', 'us']), default='jp', help='Market to check (jp or us). Defaults to jp.')
def check(market):
    """Check for upcoming earnings, price changes, MA crosses, and pullback opportunities, then send notifications

    This command checks four types of events:
    1. Upcoming earnings dates (within configured days)
    2. Significant price changes (above configured threshold)
    3. Moving average crosses (MA25 crossing MA75)
    4. Pullback opportunities (MA25 > MA75 && price < MA75)

    This command is designed to be run by cron.

    Examples:
      python main.py check                    # check JP market (default)
      python main.py check --market jp        # check JP market
      python main.py check -m us              # check US market

    Cron example (check JP market daily at 9:00 AM):
      0 9 * * * cd /path/to/stock && python main.py check
    """
    _do_check(market=market)


@cli.command()
@click.argument('output_file', type=click.Path(), default='data/watchlist.csv')
def export(output_file):
    """Export watchlist stocks to CSV file

    Exports stock code, name, and note to a CSV file.

    Examples:
      python main.py export
      python main.py export stocks.csv
    """
    stocks = db.get_all_stocks()

    if not stocks:
        click.echo("No watchlist stocks to export", err=True)
        return

    # Convert to absolute path
    output_path = Path(output_file).resolve()

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['code', 'name', 'note'])

            # Write stock data
            for stock in stocks:
                writer.writerow([stock['code'], stock.get('name', ''), stock.get('note', '')])

        click.echo(f"✓ Exported {len(stocks)} stocks to: {output_path}")

    except Exception as e:
        click.echo(f"Error: Failed to export stocks: {e}", err=True)


@cli.command('import')
@click.argument('input_file', type=click.Path(exists=True), default='data/watchlist.csv')
def import_from_file(input_file):
    """Import stocks from CSV file

    Reads stock code, name, and note from CSV file and registers them to watchlist.
    CSV file should have 'code' column (and optionally 'name' and 'note' columns).
    Market is auto-detected: 4-digit code starting with number = jp, else = us.
    Use 'update' command to fetch stock information later.

    Examples:
      python main.py import              # uses data/watchlist.csv
      python main.py import stocks.csv
    """
    try:
        result = _do_import(input_file)
        if result and result['added'] > 0:
            click.echo("\nUse 'python main.py update' to fetch stock information")
    except Exception as e:
        click.echo(f"Error: Failed to read CSV file: {e}", err=True)


@cli.command()
@click.argument('input_file', type=click.Path(exists=True), default='data/watchlist.csv')
@click.option('--market', '-m', type=click.Choice(['jp', 'us']), default='jp', help='Market to update (jp or us). Defaults to jp.')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--kabutan', '-k', is_flag=True, help='Update EPS and dividend from Kabutan even if already exists (JP only)')
def run(input_file, market, verbose, kabutan):
    """Run import, update, and check in sequence

    This command executes the following steps:
    1. Import stocks from CSV file
    2. Update stock information from API for specified market
    3. Check for upcoming earnings and send notifications

    Examples:
      python main.py run                                # uses data/watchlist.csv, update JP stocks (default)
      python main.py run --market jp                    # uses data/watchlist.csv, update JP stocks
      python main.py run -m us -v                       # update US stocks with verbose output
      python main.py run -k                             # update JP stocks and refresh Kabutan data
      python main.py run my_stocks.csv --market us -v   # custom CSV, update US stocks
    """
    # Step 1: Import
    click.echo("=" * 80)
    click.echo("STEP 1/3: Importing stocks from CSV")
    click.echo("=" * 80)
    click.echo("")

    try:
        import_result = _do_import(input_file)
        if not import_result:
            return
    except Exception as e:
        click.echo(f"Error: Failed to read CSV file: {e}", err=True)
        return

    # Step 2: Update all
    click.echo("\n")
    click.echo("=" * 80)
    click.echo(f"STEP 2/3: Updating stock information ({market.upper()} market)")
    click.echo("=" * 80)
    click.echo("")

    _do_update_all(verbose, market=market, update_kabutan=kabutan)

    # Step 3: Check
    click.echo("\n")
    click.echo("=" * 80)
    market_msg = f" ({market.upper()} market)" if market else ""
    click.echo(f"STEP 3/3: Checking for upcoming earnings{market_msg}")
    click.echo("=" * 80)
    click.echo("")

    _do_check(market=market)

    click.echo("\n")
    click.echo("=" * 80)
    click.echo("ALL STEPS COMPLETED")
    click.echo("=" * 80)


if __name__ == '__main__':
    cli()
