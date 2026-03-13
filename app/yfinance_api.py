"""Stock data retrieval module"""
import yfinance as yf
from typing import Optional, Dict
from datetime import datetime


class YFinanceAPI:
    """Stock data retrieval class"""

    @staticmethod
    def format_jp_ticker(code: str) -> str:
        """
        Convert Japanese stock code to Yahoo Finance format

        Args:
            code: Stock code (e.g., "7203", "285A", or "7203.T")

        Returns:
            Stock code in Yahoo Finance format (e.g., "7203.T", "285A.T")
        """
        # Return as-is if .T is already appended
        if code.endswith(".T"):
            return code

        # Add .T for Japanese stock codes (starts with digit)
        # This includes regular stocks (e.g., "7203") and preferred stocks (e.g., "285A")
        if code and code[0].isdigit():
            return f"{code}.T"

        # Return as-is for other cases
        return code

    @staticmethod
    def get_stock_info(code: str) -> Optional[Dict]:
        """
        Get stock information

        Args:
            code: Stock code

        Returns:
            Dictionary of stock information, or None if unable to retrieve
        """
        try:
            ticker = YFinanceAPI.format_jp_ticker(code)
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or info.get('regularMarketPrice') is None:
                return None

            # Extract necessary information
            current_price = info.get('regularMarketPrice') or info.get('currentPrice')

            # Get EPS (Earnings Per Share)
            eps = info.get('trailingEps') or info.get('forwardEps')

            # Get dividend
            dividend = info.get('dividendRate') or info.get('lastDividend')

            # Get earnings date from calendar
            earnings_date = None
            try:
                calendar = stock.calendar
                # For DataFrame case
                if calendar is not None and hasattr(calendar, 'empty') and not calendar.empty:
                    if 'Earnings Date' in calendar.index:
                        earnings_dates = calendar.loc['Earnings Date']
                        if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                            next_earnings = earnings_dates[0]
                            if hasattr(next_earnings, 'strftime'):
                                earnings_date = next_earnings.strftime('%Y-%m-%d')
                # For dict case
                elif isinstance(calendar, dict) and calendar:
                    if 'Earnings Date' in calendar:
                        earnings_date_val = calendar['Earnings Date']
                        if hasattr(earnings_date_val, 'strftime'):
                            earnings_date = earnings_date_val.strftime('%Y-%m-%d')
                        elif isinstance(earnings_date_val, (list, tuple)) and len(earnings_date_val) > 0:
                            if hasattr(earnings_date_val[0], 'strftime'):
                                earnings_date = earnings_date_val[0].strftime('%Y-%m-%d')
            except Exception:
                pass

            stock_info = {
                'code': code,
                'price': current_price,
                'eps': eps,
                'dividend': dividend,
                'earnings_date': earnings_date,
            }

            return stock_info

        except Exception as e:
            print(f"Error: Failed to retrieve stock information ({code}): {e}")
            return None

    @staticmethod
    def get_price_history(code: str, period: str = '1y') -> Optional[list]:
        """
        Get historical price data

        Args:
            code: Stock code
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

        Returns:
            List of dictionaries with keys: date, close
            Returns None if unable to retrieve
        """
        try:
            ticker = YFinanceAPI.format_jp_ticker(code)
            stock = yf.Ticker(ticker)

            # Get historical data
            hist = stock.history(period=period)

            if hist.empty or 'Close' not in hist.columns:
                return None

            # Convert to list of dictionaries
            price_history = []
            for date, row in hist.iterrows():
                price_history.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'close': row['Close']
                })

            return price_history

        except Exception as e:
            print(f"Error: Failed to retrieve price history ({code}): {e}")
            return None
