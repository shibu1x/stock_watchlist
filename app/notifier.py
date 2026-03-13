"""Discord notification module"""
import os
import requests
from typing import List, Dict
from datetime import datetime


class DiscordNotifier:
    """Discord notification class"""

    def __init__(self):
        """Initialize Discord notification"""
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")

    @staticmethod
    def _get_currency_symbol(market: str) -> str:
        """
        Get currency symbol based on market

        Args:
            market: Market type ('jp' or 'us')

        Returns:
            Currency symbol ('¥' for jp, '$' for us)
        """
        return '¥' if market == 'jp' else '$'

    @staticmethod
    def _get_stock_url(code: str, market: str) -> str:
        """
        Get stock URL based on market

        Args:
            code: Stock code
            market: Market type ('jp' or 'us')

        Returns:
            Stock URL (kabutan.jp for jp, us.kabutan.jp for us)
        """
        if market == 'jp':
            return f"https://kabutan.jp/stock/chart?code={code}"
        else:  # us
            return f"https://us.kabutan.jp/stocks/{code}/chart"

    @staticmethod
    def _build_price_fields(price, price_change_rate, per, dividend_yield, currency) -> List[Dict]:
        """
        Build standard price/PER/dividend embed fields.

        Args:
            price: Current stock price
            price_change_rate: Price change percentage
            per: Price-to-earnings ratio
            dividend_yield: Dividend yield percentage
            currency: Currency symbol

        Returns:
            List of embed field dicts
        """
        fields = []
        if price:
            price_text = f"{currency}{price:,.0f}"
            if price_change_rate is not None:
                price_text += f" ({price_change_rate:+.2f}%)"
            fields.append({"name": "Current Price", "value": price_text, "inline": True})
        if per:
            fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})
        if dividend_yield:
            fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})
        return fields

    def _send_chunked(self, embeds: List[Dict], single_content: str, multi_content: str) -> bool:
        """
        Send embeds to Discord in chunks of 10 (API limit).

        Args:
            embeds: List of embed dicts to send
            single_content: Content string (with {total} placeholder) when all fit in one message
            multi_content: Content string (with {chunk_num}, {total_chunks}, {total} placeholders)
                           when multiple messages are needed

        Returns:
            True if all chunks sent successfully
        """
        MAX_EMBEDS = 10
        total = len(embeds)
        total_chunks = (total + MAX_EMBEDS - 1) // MAX_EMBEDS
        all_successful = True

        for i in range(0, total, MAX_EMBEDS):
            chunk = embeds[i:i + MAX_EMBEDS]
            chunk_num = i // MAX_EMBEDS + 1
            if total_chunks > 1:
                content = multi_content.format(chunk_num=chunk_num, total_chunks=total_chunks, total=total)
            else:
                content = single_content.format(total=total)
            if not self.send_message(content, chunk):
                all_successful = False
                print(f"Warning: Failed to send notification chunk {chunk_num}/{total_chunks}")

        return all_successful

    def send_message(self, content: str, embeds: List[Dict] = None) -> bool:
        """
        Send message to Discord

        Args:
            content: Message body
            embeds: Embeds (optional)

        Returns:
            True if send was successful
        """
        try:
            payload = {"content": content}

            if embeds:
                payload["embeds"] = embeds

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Error: Failed to send Discord notification: {e}")
            return False

    def send_earnings_notification(self, stocks: List[Dict]) -> bool:
        """
        Send earnings date notification to Discord

        Args:
            stocks: List of stock information

        Returns:
            True if send was successful
        """
        if not stocks:
            return False

        # Sort stocks by earnings_date (nearest first)
        sorted_stocks = sorted(
            stocks,
            key=lambda s: s.get('earnings_date') or '9999-12-31'
        )

        embeds = []

        for stock in sorted_stocks:
            earnings_date = stock.get('earnings_date')
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            per = stock.get('per')
            dividend_yield = stock.get('dividend_yield')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not earnings_date:
                continue

            try:
                earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d').date()
                days_until = (earnings_dt - datetime.now().date()).days

                # Skip past earnings dates
                if days_until < 0:
                    continue

                if days_until == 0:
                    urgency = "🔴 Earnings date is today!"
                    color = 0xFF0000  # Red
                elif days_until == 1:
                    urgency = "🟠 Earnings date is tomorrow!"
                    color = 0xFF8800  # Orange
                else:
                    urgency = f"🟡 {days_until} days remaining"
                    color = 0xFFDD00  # Yellow

                fields = [
                    {"name": "Earnings Date", "value": earnings_date, "inline": True},
                    {"name": "Days Remaining", "value": urgency, "inline": True}
                ]
                fields.extend(self._build_price_fields(price, price_change_rate, per, dividend_yield, currency))

                embed = {
                    "title": f"📊 {name} ({code})",
                    "url": self._get_stock_url(code, market),
                    "color": color,
                    "fields": fields,
                    "timestamp": datetime.utcnow().isoformat()
                }

                embeds.append(embed)

            except ValueError:
                continue

        if not embeds:
            return False

        return self._send_chunked(
            embeds,
            "📢 **Earnings Date Notification** - Earnings approaching for {total} stocks",
            "📢 **Earnings Date Notification** ({chunk_num}/{total_chunks}) - Total {total} stocks"
        )

    def send_price_change_notification(self, stocks: List[Dict]) -> bool:
        """
        Send price change notification to Discord

        Args:
            stocks: List of stock information

        Returns:
            True if send was successful
        """
        if not stocks:
            return False

        # Sort: positive changes first, then negative; each group sorted by absolute value desc
        positive_changes = sorted(
            [s for s in stocks if s.get('price_change_rate', 0) > 0],
            key=lambda s: abs(s.get('price_change_rate', 0)), reverse=True
        )
        negative_changes = sorted(
            [s for s in stocks if s.get('price_change_rate', 0) < 0],
            key=lambda s: abs(s.get('price_change_rate', 0)), reverse=True
        )
        sorted_stocks = positive_changes + negative_changes

        embeds = []

        for stock in sorted_stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            per = stock.get('per')
            dividend_yield = stock.get('dividend_yield')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if price_change_rate is None:
                continue

            if price_change_rate > 0:
                color = 0x00FF00  # Green for positive change
                emoji = "📈"
            else:
                color = 0xFF0000  # Red for negative change
                emoji = "📉"

            fields = self._build_price_fields(price, price_change_rate, per, dividend_yield, currency)

            embed = {
                "title": f"{emoji} {name} ({code})",
                "url": self._get_stock_url(code, market),
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat()
            }

            embeds.append(embed)

        if not embeds:
            return False

        return self._send_chunked(
            embeds,
            "💹 **Price Change Alert** - Significant price changes detected for {total} stocks",
            "💹 **Price Change Alert** ({chunk_num}/{total_chunks}) - Total {total} stocks"
        )

    def send_ma_cross_notification(self, stocks: List[Dict]) -> bool:
        """
        Send MA cross notification to Discord

        Args:
            stocks: List of stock information with 'cross_type' field

        Returns:
            True if send was successful
        """
        if not stocks:
            return False

        embeds = []

        for stock in stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            cross_type = stock.get('cross_type')
            per = stock.get('per')
            dividend_yield = stock.get('dividend_yield')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not cross_type:
                continue

            if cross_type == 'golden':
                color = 0xFFD700  # Gold
                emoji = "🌟"
                cross_name = "Golden Cross"
                cross_desc = "MA25 crossed above MA75 (bullish signal)"
            else:  # dead cross
                color = 0x800080  # Purple
                emoji = "⚠️"
                cross_name = "Dead Cross"
                cross_desc = "MA25 crossed below MA75 (bearish signal)"

            fields = [{"name": "Signal Type", "value": cross_desc, "inline": False}]
            fields.extend(self._build_price_fields(price, price_change_rate, per, dividend_yield, currency))

            embed = {
                "title": f"{emoji} {cross_name}: {name} ({code})",
                "url": self._get_stock_url(code, market),
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat()
            }

            embeds.append(embed)

        if not embeds:
            return False

        return self._send_chunked(
            embeds,
            "📊 **Moving Average Cross Alert** - MA cross detected for {total} stocks",
            "📊 **Moving Average Cross Alert** ({chunk_num}/{total_chunks}) - Total {total} stocks"
        )

    def send_pullback_notification(self, stocks: List[Dict]) -> bool:
        """
        Send pullback opportunity notification to Discord

        Args:
            stocks: List of stock information (MA25 > MA75 && price < MA75)

        Returns:
            True if send was successful
        """
        if not stocks:
            return False

        embeds = []

        for stock in stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            per = stock.get('per')
            dividend_yield = stock.get('dividend_yield')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not price:
                continue

            color = 0x00CED1  # DarkTurquoise
            emoji = "🎯"

            fields = [
                {"name": "Signal Type", "value": "Pullback Opportunity (MA25 > MA75, Price < MA75)", "inline": False}
            ]
            fields.extend(self._build_price_fields(price, price_change_rate, per, dividend_yield, currency))

            embed = {
                "title": f"{emoji} Pullback Opportunity: {name} ({code})",
                "url": self._get_stock_url(code, market),
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat()
            }

            embeds.append(embed)

        if not embeds:
            return False

        return self._send_chunked(
            embeds,
            "🎯 **Pullback Opportunity Alert** - Potential buying opportunities for {total} stocks",
            "🎯 **Pullback Opportunity Alert** ({chunk_num}/{total_chunks}) - Total {total} stocks"
        )

    def send_breakout_notification(self, stocks: List[Dict]) -> bool:
        """
        Send price breakout notification to Discord

        Args:
            stocks: List of stock information with high_breakout or low_breakout

        Returns:
            True if send was successful
        """
        if not stocks:
            return False

        # Separate high and low breakouts, sort by period (longest first)
        high_breakouts = sorted(
            [s for s in stocks if s.get('high_breakout')],
            key=lambda s: s.get('high_breakout', 0), reverse=True
        )
        low_breakouts = sorted(
            [s for s in stocks if s.get('low_breakout')],
            key=lambda s: s.get('low_breakout', 0), reverse=True
        )
        sorted_stocks = high_breakouts + low_breakouts

        embeds = []

        for stock in sorted_stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            high_breakout = stock.get('high_breakout')
            low_breakout = stock.get('low_breakout')
            per = stock.get('per')
            dividend_yield = stock.get('dividend_yield')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if high_breakout and low_breakout:
                color = 0xFFD700  # Gold
                emoji = "⚡"
                breakout_type = "High & Low Breakout"
                breakout_desc = f"High: {high_breakout} days, Low: {low_breakout} days"
            elif high_breakout:
                color = 0x00FF00  # Green
                emoji = "🚀"
                breakout_type = "High Breakout"
                breakout_desc = f"{high_breakout}-day high"
            else:
                color = 0xFF0000  # Red
                emoji = "📉"
                breakout_type = "Low Breakout"
                breakout_desc = f"{low_breakout}-day low"

            fields = [{"name": "Breakout Type", "value": breakout_desc, "inline": False}]
            fields.extend(self._build_price_fields(price, price_change_rate, per, dividend_yield, currency))

            embed = {
                "title": f"{emoji} {breakout_type}: {name} ({code})",
                "url": self._get_stock_url(code, market),
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat()
            }

            embeds.append(embed)

        if not embeds:
            return False

        return self._send_chunked(
            embeds,
            "🔔 **Price Breakout Alert** - Breakouts detected for {total} stocks",
            "🔔 **Price Breakout Alert** ({chunk_num}/{total_chunks}) - Total {total} stocks"
        )

    def send_test_notification(self) -> bool:
        """
        Send test notification to Discord

        Returns:
            True if send was successful
        """
        embed = {
            "title": "✅ Test Notification",
            "description": "Discord notification feature is working properly.",
            "color": 0x00FF00,  # Green
            "fields": [
                {
                    "name": "Sent at",
                    "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "inline": False
                }
            ],
            "footer": {
                "text": "Japanese Stock Watchlist App"
            }
        }

        return self.send_message("🔔 **Test Notification**", [embed])

    @staticmethod
    def validate_config() -> tuple[bool, str]:
        """
        Check if Discord configuration is correct

        Returns:
            (validity, message)
        """
        if not os.getenv("DISCORD_WEBHOOK_URL", ""):
            return False, "DISCORD_WEBHOOK_URL is not set"
        return True, "Discord configuration is correct"
