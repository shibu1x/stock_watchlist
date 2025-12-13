"""Stock data retrieval module"""
import yfinance as yf
from typing import Optional, Dict
from datetime import datetime


class StockAPI:
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
            ticker = StockAPI.format_jp_ticker(code)
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

            # Calculate moving averages
            ma25 = None
            ma75 = None
            prev_ma25 = None
            prev_ma75 = None
            try:
                # Get historical data (need 75 days + buffer for calculation)
                hist = stock.history(period='6mo')
                if not hist.empty and 'Close' in hist.columns:
                    # Calculate 25-day moving average
                    if len(hist) >= 25:
                        ma_series_25 = hist['Close'].rolling(window=25).mean()
                        ma25 = ma_series_25.iloc[-1]
                        # Get previous day's MA25 if available
                        if len(ma_series_25) >= 2:
                            prev_ma25 = ma_series_25.iloc[-2]

                    # Calculate 75-day moving average
                    if len(hist) >= 75:
                        ma_series_75 = hist['Close'].rolling(window=75).mean()
                        ma75 = ma_series_75.iloc[-1]
                        # Get previous day's MA75 if available
                        if len(ma_series_75) >= 2:
                            prev_ma75 = ma_series_75.iloc[-2]
            except Exception as e:
                print(f"Warning: Failed to calculate moving averages ({code}): {e}")

            stock_info = {
                'code': code,
                'price': current_price,
                'prev_price': info.get('previousClose'),
                'eps': eps,
                'dividend': dividend,
                'ma25': ma25,
                'ma75': ma75,
                'prev_ma25': prev_ma25,
                'prev_ma75': prev_ma75,
                'earnings_date': earnings_date,
            }

            return stock_info

        except Exception as e:
            print(f"Error: Failed to retrieve stock information ({code}): {e}")
            return None
