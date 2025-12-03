"""Database operations module"""
import sqlite3
from datetime import datetime
from typing import List, Optional
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
                earnings_date TEXT,
                price REAL,
                prev_price REAL,
                price_change_rate REAL,
                dividend REAL,
                dividend_yield REAL,
                eps REAL,
                per REAL,
                ma25 REAL,
                ma75 REAL,
                prev_ma25 REAL,
                prev_ma75 REAL,
                note TEXT,
                added_date TEXT NOT NULL,
                last_updated TEXT,
                last_api_call TEXT
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code ON watchlist(code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_earnings_date ON watchlist(earnings_date)
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
                  earnings_date: str = None, price: float = None,
                  prev_price: float = None, price_change_rate: float = None,
                  dividend: float = None, dividend_yield: float = None,
                  eps: float = None, per: float = None,
                  ma25: float = None, ma75: float = None,
                  prev_ma25: float = None, prev_ma75: float = None,
                  note: str = None, last_api_call: str = None) -> bool:
        """
        Add a stock to the watchlist

        Args:
            code: Stock code
            name: Stock name
            market: Market (jp or us)
            earnings_date: Earnings date (YYYY-MM-DD format)
            price: Current stock price
            prev_price: Previous day's closing price
            price_change_rate: Stock price change percentage
            dividend: Expected dividend amount
            dividend_yield: Dividend yield percentage
            eps: Earnings per share (trailing 12 months)
            per: Price-to-earnings ratio
            ma25: 25-day moving average
            ma75: 75-day moving average
            prev_ma25: Previous 25-day moving average
            prev_ma75: Previous 75-day moving average
            note: Note/remarks
            last_api_call: Last API call timestamp

        Returns:
            True if successfully added
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            # Only set last_updated if we have API data (price, earnings_date, etc.)
            # If only code/name are provided, keep last_updated as NULL so update will fetch data
            has_api_data = any([
                earnings_date, price, prev_price, dividend, dividend_yield,
                eps, per, ma25, ma75
            ])
            last_updated_value = now if has_api_data else None

            cursor.execute("""
                INSERT INTO watchlist
                (code, name, market, earnings_date, price, prev_price,
                 price_change_rate, dividend, dividend_yield, eps, per, ma25, ma75, prev_ma25, prev_ma75, note, added_date, last_updated, last_api_call)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, market, earnings_date, price, prev_price,
                  price_change_rate, dividend, dividend_yield, eps, per, ma25, ma75, prev_ma25, prev_ma75, note, now, last_updated_value, last_api_call))

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
                     prev_price: float = None, price_change_rate: float = None,
                     dividend: float = None, dividend_yield: float = None,
                     eps: float = None, per: float = None,
                     ma25: float = None, ma75: float = None,
                     prev_ma25: float = None, prev_ma75: float = None,
                     note: str = None, last_api_call: str = None) -> bool:
        """
        Update stock information in the watchlist

        Args:
            code: Stock code
            name: Stock name
            market: Market (jp or us)
            earnings_date: Earnings date
            price: Current stock price
            prev_price: Previous day's closing price
            price_change_rate: Stock price change percentage
            dividend: Expected dividend amount
            dividend_yield: Dividend yield percentage
            eps: Earnings per share (trailing 12 months)
            per: Price-to-earnings ratio
            ma25: 25-day moving average
            ma75: 75-day moving average
            prev_ma25: Previous 25-day moving average
            prev_ma75: Previous 75-day moving average
            note: Note/remarks
            last_api_call: Last API call timestamp

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

        if prev_price is not None:
            updates.append("prev_price = ?")
            params.append(prev_price)

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

        if ma25 is not None:
            updates.append("ma25 = ?")
            params.append(ma25)

        if ma75 is not None:
            updates.append("ma75 = ?")
            params.append(ma75)

        if prev_ma25 is not None:
            updates.append("prev_ma25 = ?")
            params.append(prev_ma25)

        if prev_ma75 is not None:
            updates.append("prev_ma75 = ?")
            params.append(prev_ma75)

        if note is not None:
            updates.append("note = ?")
            params.append(note)

        if last_api_call is not None:
            updates.append("last_api_call = ?")
            params.append(last_api_call)

        if not updates:
            cursor.close()
            conn.close()
            return False

        updates.append("last_updated = ?")
        params.append(datetime.now().isoformat())
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

    def get_stocks_with_upcoming_earnings(self, days: int = 7, market: str = 'jp') -> List[dict]:
        """
        Get stocks with upcoming earnings dates

        Args:
            days: Number of days within which to look for earnings dates
            market: Market to filter (jp or us). Defaults to 'jp'.

        Returns:
            List of stocks with upcoming earnings dates
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM watchlist
            WHERE earnings_date IS NOT NULL
            AND earnings_date BETWEEN date('now') AND date('now', '+' || ? || ' days')
            AND market = ?
            ORDER BY earnings_date
        """, (days, market))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]

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

        cursor.execute("""
            SELECT * FROM watchlist
            WHERE ma25 IS NOT NULL
            AND ma75 IS NOT NULL
            AND prev_ma25 IS NOT NULL
            AND prev_ma75 IS NOT NULL
            AND market = ?
        """, (market,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Detect MA crosses
        stocks_with_cross = []
        for row in rows:
            stock = dict(row)
            ma25 = stock['ma25']
            ma75 = stock['ma75']
            prev_ma25 = stock['prev_ma25']
            prev_ma75 = stock['prev_ma75']

            # Golden cross: prev_ma25 <= prev_ma75 and ma25 > ma75
            if prev_ma25 <= prev_ma75 and ma25 > ma75:
                stock['cross_type'] = 'golden'
                stocks_with_cross.append(stock)
            # Dead cross: prev_ma25 >= prev_ma75 and ma25 < ma75
            elif prev_ma25 >= prev_ma75 and ma25 < ma75:
                stock['cross_type'] = 'dead'
                stocks_with_cross.append(stock)

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

        cursor.execute("""
            SELECT * FROM watchlist
            WHERE ma25 IS NOT NULL
            AND ma75 IS NOT NULL
            AND price IS NOT NULL
            AND ma25 > ma75
            AND price < ma75
            AND market = ?
            ORDER BY code
        """, (market,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert sqlite3.Row to dict
        return [dict(row) for row in rows]
