"""Database operations module"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from config import Config
from pathlib import Path


class Database:
    """SQLite database management class"""

    def __init__(self, db_path: str = None):
        """
        Initialize database

        Args:
            db_path: Database file path
        """
        self.db_path = db_path or Config.DB_PATH
        self._init_database()

    def _init_database(self):
        """Initialize database and tables"""
        # Create database directory
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = self.get_connection()
        cursor = conn.cursor()

        # Watchlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT,
                market TEXT,
                per REAL,
                dividend_yield REAL,
                high_breakout INTEGER,
                low_breakout INTEGER,
                price REAL,
                price_change_rate REAL,
                eps REAL,
                dividend REAL,
                earnings_date TEXT,
                note TEXT
            )
        """)

        # Price history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                stock_code TEXT NOT NULL,
                date TEXT NOT NULL,
                close REAL NOT NULL,
                ma25 REAL,
                ma75 REAL,
                ma25_deviation REAL,
                ma75_deviation REAL,
                PRIMARY KEY (stock_code, date)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code ON watchlist(code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_earnings_date ON watchlist(earnings_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_stock ON price_history(stock_code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(date)
        """)

        conn.commit()
        cursor.close()
        conn.close()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_stock(self, code: str, name: str = None, market: str = None,
                  note: str = None) -> bool:
        """
        Add a stock to the watchlist

        Args:
            code: Stock code
            name: Stock name
            market: Market (jp or us)
            note: Note/remarks

        Returns:
            True if successfully added
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO watchlist (code, name, market, note)
                VALUES (?, ?, ?, ?)
            """, (code, name, market, note))

            conn.commit()
            cursor.close()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_stock(self, code: str) -> bool:
        """
        Remove a stock from the watchlist

        Args:
            code: Stock code

        Returns:
            True if successfully removed
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM watchlist WHERE code = ?", (code,))
        deleted = cursor.rowcount > 0

        conn.commit()
        cursor.close()
        conn.close()
        return deleted

    def update_stock(self, code: str, name: str = None, market: str = None,
                     earnings_date: str = None, price: float = None,
                     price_change_rate: float = None,
                     dividend: float = None, dividend_yield: float = None,
                     eps: float = None, per: float = None,
                     high_breakout: int = None, low_breakout: int = None,
                     update_breakouts: bool = False,
                     note: str = None) -> bool:
        """
        Update stock information in the watchlist

        Args:
            code: Stock code
            name: Stock name
            market: Market (jp or us)
            earnings_date: Earnings date
            price: Current stock price
            price_change_rate: Stock price change percentage
            dividend: Expected dividend amount
            dividend_yield: Dividend yield percentage
            eps: Earnings per share (trailing 12 months)
            per: Price-to-earnings ratio
            high_breakout: High price breakout period (30, 90, 180, 360 days)
            low_breakout: Low price breakout period (30, 90, 180, 360 days)
            update_breakouts: If True, always update breakout fields (even if None/NULL)
            note: Note/remarks

        Returns:
            True if successfully updated
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if market is not None:
            updates.append("market = ?")
            params.append(market)

        if earnings_date is not None:
            updates.append("earnings_date = ?")
            params.append(earnings_date)

        if price is not None:
            updates.append("price = ?")
            params.append(price)

        if price_change_rate is not None:
            updates.append("price_change_rate = ?")
            params.append(price_change_rate)

        if dividend is not None:
            updates.append("dividend = ?")
            params.append(dividend)

        if dividend_yield is not None:
            updates.append("dividend_yield = ?")
            params.append(dividend_yield)

        if eps is not None:
            updates.append("eps = ?")
            params.append(eps)

        if per is not None:
            updates.append("per = ?")
            params.append(per)

        # For breakout fields, update them if flag is set (even if None to clear previous values)
        # or if they have non-None values
        if update_breakouts or high_breakout is not None:
            updates.append("high_breakout = ?")
            params.append(high_breakout)

        if update_breakouts or low_breakout is not None:
            updates.append("low_breakout = ?")
            params.append(low_breakout)

        if note is not None:
            updates.append("note = ?")
            params.append(note)

        if not updates:
            cursor.close()
            conn.close()
            return False

        params.append(code)

        query = f"UPDATE watchlist SET {', '.join(updates)} WHERE code = ?"
        cursor.execute(query, params)

        updated = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        return updated

    def get_all_stocks(self) -> List[dict]:
        """
        Get all stocks from the watchlist

        Returns:
            List of stocks in the watchlist
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM watchlist ORDER BY code")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]

    def get_stock(self, code: str) -> Optional[dict]:
        """
        Get a specific stock from the watchlist

        Args:
            code: Stock code

        Returns:
            Dictionary containing stock information, or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM watchlist WHERE code = ?", (code,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        return dict(row) if row else None

    def get_stocks_with_price_change(self, threshold: float = 5.0, market: str = 'jp') -> List[dict]:
        """
        Get stocks with significant price changes

        Args:
            threshold: Price change threshold percentage (absolute value)
            market: Market to filter (jp or us). Defaults to 'jp'.

        Returns:
            List of stocks with significant price changes
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM watchlist
            WHERE price_change_rate IS NOT NULL
            AND ABS(price_change_rate) >= ?
            AND market = ?
            ORDER BY ABS(price_change_rate) DESC
        """, (threshold, market))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]

    def get_stocks_with_ma_cross(self, market: str = 'jp') -> List[dict]:
        """
        Get stocks where MA25 and MA75 have crossed

        Args:
            market: Market to filter (jp or us). Defaults to 'jp'.

        Returns:
            List of stocks with MA cross, each containing 'cross_type' field:
            - 'golden': MA25 crossed above MA75 (bullish signal)
            - 'dead': MA25 crossed below MA75 (bearish signal)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all stocks for the specified market
        cursor.execute("SELECT * FROM watchlist WHERE market = ?", (market,))
        stocks = cursor.fetchall()

        # Detect MA crosses
        stocks_with_cross = []
        for stock_row in stocks:
            stock = dict(stock_row)
            stock_code = stock['code']

            # Get latest 2 price history records with MA data
            cursor.execute("""
                SELECT date, ma25, ma75
                FROM price_history
                WHERE stock_code = ?
                AND ma25 IS NOT NULL
                AND ma75 IS NOT NULL
                ORDER BY date DESC
                LIMIT 2
            """, (stock_code,))

            ma_records = cursor.fetchall()

            # Need at least 2 records to detect cross
            if len(ma_records) < 2:
                continue

            # [0] is latest, [1] is previous
            latest = dict(ma_records[0])
            previous = dict(ma_records[1])

            ma25 = latest['ma25']
            ma75 = latest['ma75']
            prev_ma25 = previous['ma25']
            prev_ma75 = previous['ma75']

            # Golden cross: prev_ma25 <= prev_ma75 and ma25 > ma75
            if prev_ma25 <= prev_ma75 and ma25 > ma75:
                stock['cross_type'] = 'golden'
                stocks_with_cross.append(stock)
            # Dead cross: prev_ma25 >= prev_ma75 and ma25 < ma75
            elif prev_ma25 >= prev_ma75 and ma25 < ma75:
                stock['cross_type'] = 'dead'
                stocks_with_cross.append(stock)

        cursor.close()
        conn.close()

        return stocks_with_cross

    def get_stocks_with_pullback_opportunity(self, market: str = 'jp') -> List[dict]:
        """
        Get stocks with pullback opportunity (MA25 > MA75 && price < MA75)

        This condition indicates a potential buying opportunity where:
        - MA25 is above MA75 (bullish trend)
        - Current price is below MA75 (temporary pullback)

        Args:
            market: Market to filter (jp or us). Defaults to 'jp'.

        Returns:
            List of stocks meeting the pullback opportunity criteria
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all stocks for the specified market with price data
        cursor.execute("""
            SELECT * FROM watchlist
            WHERE market = ?
            AND price IS NOT NULL
            ORDER BY code
        """, (market,))

        stocks = cursor.fetchall()

        # Filter stocks with pullback opportunity
        pullback_stocks = []
        for stock_row in stocks:
            stock = dict(stock_row)
            stock_code = stock['code']
            price = stock['price']

            # Get latest MA data from price_history
            cursor.execute("""
                SELECT ma25, ma75
                FROM price_history
                WHERE stock_code = ?
                AND ma25 IS NOT NULL
                AND ma75 IS NOT NULL
                ORDER BY date DESC
                LIMIT 1
            """, (stock_code,))

            ma_record = cursor.fetchone()

            # Check pullback condition
            if ma_record:
                ma25 = ma_record['ma25']
                ma75 = ma_record['ma75']

                # MA25 > MA75 && price < MA75
                if ma25 > ma75 and price < ma75:
                    pullback_stocks.append(stock)

        cursor.close()
        conn.close()

        return pullback_stocks

    def get_stocks_with_breakouts(self, market: str = 'jp') -> List[dict]:
        """
        Get stocks with price breakouts (high_breakout or low_breakout is not NULL)

        Args:
            market: Market to filter (jp or us). Defaults to 'jp'.

        Returns:
            List of stocks with breakouts
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM watchlist
            WHERE (high_breakout IS NOT NULL OR low_breakout IS NOT NULL)
            AND market = ?
            ORDER BY
                CASE
                    WHEN high_breakout IS NOT NULL THEN high_breakout
                    ELSE 0
                END DESC,
                CASE
                    WHEN low_breakout IS NOT NULL THEN low_breakout
                    ELSE 0
                END DESC,
                code
        """, (market,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]

    def save_price_history_bulk(self, price_data: List[Dict]) -> int:
        """
        Save multiple historical price records in bulk

        Deletes existing price history for the stock codes before inserting new data.

        Args:
            price_data: List of dictionaries with keys: stock_code, date, close

        Returns:
            Number of records successfully saved
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get unique stock codes from price_data
            stock_codes = set(data['stock_code'] for data in price_data)

            # Delete existing price history for these stock codes
            for stock_code in stock_codes:
                cursor.execute("DELETE FROM price_history WHERE stock_code = ?", (stock_code,))

            # Insert new price history data
            saved_count = 0
            for data in price_data:
                try:
                    cursor.execute("""
                        INSERT INTO price_history (stock_code, date, close)
                        VALUES (?, ?, ?)
                    """, (data['stock_code'], data['date'], data['close']))
                    saved_count += 1
                except Exception as e:
                    print(f"Warning: Failed to save price history record: {e}")
                    continue

            conn.commit()
            cursor.close()
            conn.close()
            return saved_count
        except Exception as e:
            print(f"Error: Failed to save price history in bulk: {e}")
            return 0

    def get_price_history(self, stock_code: str, start_date: str = None,
                         end_date: str = None, limit: int = None) -> List[dict]:
        """
        Get historical price data for a stock

        Args:
            stock_code: Stock code
            start_date: Start date (YYYY-MM-DD format, optional)
            end_date: End date (YYYY-MM-DD format, optional)
            limit: Maximum number of records to return (optional)

        Returns:
            List of historical price records (sorted by date descending)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM price_history WHERE stock_code = ?"
        params = [stock_code]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]

    def calculate_moving_averages(self, stock_code: str) -> bool:
        """
        Calculate moving averages and deviations from price history and save to latest 2 records

        Args:
            stock_code: Stock code

        Returns:
            True if successfully calculated and saved, False otherwise
        """
        try:
            # Get latest 76 days of price history (75 for MA75 + 1 for previous day comparison)
            history = self.get_price_history(stock_code, limit=76)

            if len(history) < 25:
                return False

            # Reverse to get chronological order (oldest to newest)
            history.reverse()

            # Extract close prices
            close_prices = [h['close'] for h in history]

            conn = self.get_connection()
            cursor = conn.cursor()

            # Calculate and update MA for latest date
            if len(close_prices) >= 25:
                latest_date = history[-1]['date']
                latest_close = history[-1]['close']
                latest_ma25 = sum(close_prices[-25:]) / 25
                latest_ma75 = None
                latest_ma25_deviation = None
                latest_ma75_deviation = None

                # Calculate deviation from MA25
                if latest_ma25 > 0:
                    latest_ma25_deviation = ((latest_close - latest_ma25) / latest_ma25) * 100

                if len(close_prices) >= 75:
                    latest_ma75 = sum(close_prices[-75:]) / 75
                    # Calculate deviation from MA75
                    if latest_ma75 > 0:
                        latest_ma75_deviation = ((latest_close - latest_ma75) / latest_ma75) * 100

                cursor.execute("""
                    UPDATE price_history
                    SET ma25 = ?, ma75 = ?, ma25_deviation = ?, ma75_deviation = ?
                    WHERE stock_code = ? AND date = ?
                """, (latest_ma25, latest_ma75, latest_ma25_deviation, latest_ma75_deviation, stock_code, latest_date))

            # Calculate and update MA for previous date (if we have enough data)
            if len(close_prices) >= 26:
                prev_date = history[-2]['date']
                prev_close = history[-2]['close']
                prev_ma25 = sum(close_prices[-26:-1]) / 25
                prev_ma75 = None
                prev_ma25_deviation = None
                prev_ma75_deviation = None

                # Calculate deviation from MA25
                if prev_ma25 > 0:
                    prev_ma25_deviation = ((prev_close - prev_ma25) / prev_ma25) * 100

                if len(close_prices) >= 76:
                    prev_ma75 = sum(close_prices[-76:-1]) / 75
                    # Calculate deviation from MA75
                    if prev_ma75 > 0:
                        prev_ma75_deviation = ((prev_close - prev_ma75) / prev_ma75) * 100

                cursor.execute("""
                    UPDATE price_history
                    SET ma25 = ?, ma75 = ?, ma25_deviation = ?, ma75_deviation = ?
                    WHERE stock_code = ? AND date = ?
                """, (prev_ma25, prev_ma75, prev_ma25_deviation, prev_ma75_deviation, stock_code, prev_date))

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            print(f"Error: Failed to calculate moving averages ({stock_code}): {e}")
            return False

    def calculate_price_change_rate(self, stock_code: str) -> Optional[float]:
        """
        Calculate price change rate from price history

        Args:
            stock_code: Stock code

        Returns:
            Price change rate percentage, or None if insufficient data
        """
        try:
            # Get latest 2 days of price history
            history = self.get_price_history(stock_code, limit=2)

            if len(history) < 2:
                return None

            # history is sorted DESC, so [0] is latest, [1] is previous
            latest_close = history[0]['close']
            previous_close = history[1]['close']

            if previous_close <= 0:
                return None

            # Calculate change rate: ((latest - previous) / previous) * 100
            price_change_rate = ((latest_close - previous_close) / previous_close) * 100

            return price_change_rate

        except Exception as e:
            print(f"Error: Failed to calculate price change rate ({stock_code}): {e}")
            return None

    def calculate_price_breakouts(self, stock_code: str, current_price: float) -> Optional[Dict]:
        """
        Calculate price breakouts from price history

        Checks if the current price is a new high or low for periods: 30, 90, 180, 360 days
        Returns the longest period for which the breakout occurred

        Args:
            stock_code: Stock code
            current_price: Current stock price

        Returns:
            Dictionary with keys: high_breakout, low_breakout (values: 30, 90, 180, 360, or None)
            Returns None if insufficient data
        """
        if not current_price:
            return None

        try:
            # Get all available price history (up to 1 year)
            history = self.get_price_history(stock_code)

            if not history:
                return None

            # Get the latest date (most recent price date)
            latest_date_str = history[0]['date']  # Already sorted DESC
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d').date()

            # Define periods to check (in ascending order)
            periods = [30, 90, 180, 360]

            high_breakout = None
            low_breakout = None

            # Check each period (from longest to shortest)
            for period in reversed(periods):
                # Calculate the start date for this period
                start_date = latest_date - timedelta(days=period)
                start_date_str = start_date.strftime('%Y-%m-%d')

                # Get prices within this period (excluding the latest date itself)
                period_prices = []
                for h in history:
                    h_date = h['date']
                    # Include prices from start_date to before latest_date
                    if start_date_str <= h_date < latest_date_str:
                        period_prices.append(h['close'])

                # Need at least some data to compare
                if not period_prices:
                    continue

                max_price = max(period_prices)
                min_price = min(period_prices)

                # Check if current price breaks the high
                if high_breakout is None and current_price > max_price:
                    high_breakout = period

                # Check if current price breaks the low
                if low_breakout is None and current_price < min_price:
                    low_breakout = period

            return {
                'high_breakout': high_breakout,
                'low_breakout': low_breakout
            }

        except Exception as e:
            print(f"Error: Failed to calculate price breakouts ({stock_code}): {e}")
            return None

    def is_market_closed(self, market: str) -> bool:
        """
        Check if the market is closed based on the latest price data

        Args:
            market: Market type (jp or us)

        Returns:
            True if market is closed (no recent price data), False if open
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get all stock codes for the specified market
            cursor.execute("SELECT code FROM watchlist WHERE market = ?", (market,))
            stock_codes = [row['code'] for row in cursor.fetchall()]

            if not stock_codes:
                # No stocks in this market
                cursor.close()
                conn.close()
                return True

            # Get the latest price history date for any stock in this market
            placeholders = ','.join(['?'] * len(stock_codes))
            cursor.execute(f"""
                SELECT MAX(date) as latest_date
                FROM price_history
                WHERE stock_code IN ({placeholders})
            """, stock_codes)

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if not result or not result['latest_date']:
                # No price history data
                return True

            latest_date_str = result['latest_date']
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d').date()
            today = datetime.now().date()

            # JP market: closed if latest_date < today
            if market == 'jp':
                return latest_date < today

            # US market: closed if latest_date < yesterday
            elif market == 'us':
                yesterday = today - timedelta(days=1)
                return latest_date < yesterday

            # Unknown market
            return True

        except Exception as e:
            print(f"Error: Failed to check market status ({market}): {e}")
            return True  # Assume closed on error
