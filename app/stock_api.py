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
            dividend_rate = info.get('dividendRate')
            dividend_yield = info.get('dividendYield')

            # Get EPS from yfinance
            trailing_eps = info.get('trailingEps')
            forward_eps = info.get('forwardEps')
            eps = trailing_eps if trailing_eps else forward_eps

            # Calculate dividend yield if we have dividend but not yield
            if dividend_rate and current_price and not dividend_yield:
                dividend_yield = (dividend_rate / current_price) * 100

            # Calculate PER from price and EPS if both are available
            per = None
            if eps and current_price and eps > 0:
                per = current_price / eps
            else:
                # Fallback to yfinance PER if calculation not possible
                trailing_pe = info.get('trailingPE')
                forward_pe = info.get('forwardPE')
                per = trailing_pe if trailing_pe else forward_pe

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
                'name': info.get('shortName') or info.get('longName', ''),
                'price': current_price,
                'prev_price': info.get('previousClose'),
                'dividend': dividend_rate,
                'dividend_yield': dividend_yield,
                'eps': eps,
                'per': per,
                'ma25': ma25,
                'ma75': ma75,
                'prev_ma25': prev_ma25,
                'prev_ma75': prev_ma75,
                'market_cap': info.get('marketCap'),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
            }

            return stock_info

        except Exception as e:
            print(f"Error: Failed to retrieve stock information ({code}): {e}")
            return None

    @staticmethod
    def get_stock_name(code: str) -> Optional[str]:
        """
        Get stock name

        Args:
            code: Stock code

        Returns:
            Stock name, or None if unable to retrieve
        """
        info = StockAPI.get_stock_info(code)
        return info['name'] if info else None

    @staticmethod
    def get_earnings_date(code: str, verbose: bool = False) -> Optional[str]:
        """
        Get earnings date from yfinance

        Args:
            code: Stock code
            verbose: Display detailed logs

        Returns:
            Earnings date (YYYY-MM-DD format), or None if unable to retrieve
        """
        # Normalize to 4-digit number only
        code = code.replace('.T', '')

        if verbose:
            print(f"Retrieving earnings date: {code}")

        try:
            ticker = StockAPI.format_jp_ticker(code)
            stock = yf.Ticker(ticker)

            # Get earnings calendar
            try:
                calendar = stock.calendar
                # For DataFrame case
                if calendar is not None and hasattr(calendar, 'empty') and not calendar.empty:
                    if 'Earnings Date' in calendar.index:
                        earnings_dates = calendar.loc['Earnings Date']
                        if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                            next_earnings = earnings_dates[0]
                            if hasattr(next_earnings, 'strftime'):
                                if verbose:
                                    print(f"  ✓ Successfully retrieved from yfinance: {next_earnings.strftime('%Y-%m-%d')}")
                                return next_earnings.strftime('%Y-%m-%d')
                # For dict case
                elif isinstance(calendar, dict) and calendar:
                    if 'Earnings Date' in calendar:
                        earnings_date = calendar['Earnings Date']
                        if hasattr(earnings_date, 'strftime'):
                            if verbose:
                                print(f"  ✓ Successfully retrieved from yfinance: {earnings_date.strftime('%Y-%m-%d')}")
                            return earnings_date.strftime('%Y-%m-%d')
                        elif isinstance(earnings_date, (list, tuple)) and len(earnings_date) > 0:
                            if hasattr(earnings_date[0], 'strftime'):
                                if verbose:
                                    print(f"  ✓ Successfully retrieved from yfinance: {earnings_date[0].strftime('%Y-%m-%d')}")
                                return earnings_date[0].strftime('%Y-%m-%d')
            except:
                pass

            # If unable to retrieve from calendar, try to get from info
            info = stock.info
            if isinstance(info, dict) and 'earningsDate' in info and info['earningsDate']:
                earnings_timestamp = info['earningsDate']
                if isinstance(earnings_timestamp, list) and len(earnings_timestamp) > 0:
                    earnings_timestamp = earnings_timestamp[0]
                if isinstance(earnings_timestamp, int):
                    earnings_date = datetime.fromtimestamp(earnings_timestamp)
                    if verbose:
                        print(f"  ✓ Successfully retrieved from yfinance: {earnings_date.strftime('%Y-%m-%d')}")
                    return earnings_date.strftime('%Y-%m-%d')

            if verbose:
                print(f"  ✗ Failed to retrieve from yfinance")
            return None

        except Exception as e:
            if verbose:
                print(f"  ✗ yfinance error: {e}")
            else:
                print(f"Failed to retrieve from yfinance ({code}): {e}")
            return None

    @staticmethod
    def validate_stock_code(code: str) -> bool:
        """
        Check if stock code is valid

        Args:
            code: Stock code

        Returns:
            True if stock code is valid
        """
        info = StockAPI.get_stock_info(code)
        return info is not None

    @staticmethod
    def get_stock_summary(code: str) -> Optional[str]:
        """
        Get stock summary

        Args:
            code: Stock code

        Returns:
            Summary string
        """
        info = StockAPI.get_stock_info(code)
        if not info:
            return None

        summary = f"{info['name']} ({code})"

        if info.get('price'):
            summary += f"\nCurrent Price: ¥{info['price']:,.0f}"

        if info.get('prev_price'):
            change = info['price'] - info['prev_price']
            change_pct = (change / info['prev_price']) * 100
            summary += f" ({change:+,.0f} / {change_pct:+.2f}%)"

        if info.get('sector'):
            summary += f"\nSector: {info['sector']}"

        if info.get('industry'):
            summary += f"\nIndustry: {info['industry']}"

        if info.get('dividend'):
            summary += f"\nDividend: ¥{info['dividend']:,.2f}"
            if info.get('dividend_yield'):
                summary += f" (Yield: {info['dividend_yield']:.2f}%)"
        elif info.get('dividend_yield'):
            summary += f"\nDividend Yield: {info['dividend_yield']:.2f}%"

        if info.get('eps'):
            summary += f"\nEPS (Trailing): ¥{info['eps']:,.2f}"
            if info.get('per'):
                summary += f" (PER: {info['per']:.2f})"
        elif info.get('per'):
            summary += f"\nPER: {info['per']:.2f}"

        return summary
