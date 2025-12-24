"""Discord notification module"""
import requests
from typing import List, Dict
from datetime import datetime
from config import Config


class DiscordNotifier:
    """Discord notification class"""

    def __init__(self):
        """Initialize Discord notification"""
        self.webhook_url = Config.DISCORD_WEBHOOK_URL

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

        # Create embedded messages
        embeds = []

        for stock in sorted_stocks:
            earnings_date = stock.get('earnings_date')
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            dividend = stock.get('dividend')
            dividend_yield = stock.get('dividend_yield')
            eps = stock.get('eps')
            per = stock.get('per')
            ma25 = stock.get('ma25')
            ma75 = stock.get('ma75')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not earnings_date:
                continue

            # Calculate days until earnings date
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

                # Create embedded fields
                fields = [
                    {"name": "Earnings Date", "value": earnings_date, "inline": True},
                    {"name": "Days Remaining", "value": urgency, "inline": True}
                ]

                # Add stock price information if available
                if price:
                    price_text = f"{currency}{price:,.0f}"
                    if price_change_rate is not None:
                        price_text += f" ({price_change_rate:+.2f}%)"
                    fields.append({"name": "Current Price", "value": price_text, "inline": True})

                # Add PER information if available
                if per:
                    fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})

                # Add dividend information if available
                if dividend_yield:
                    fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})

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

        # Discord API limitation: max 10 embeds per message
        # Split embeds into chunks of 10 and send multiple messages if needed
        MAX_EMBEDS_PER_MESSAGE = 10
        total_stocks = len(embeds)
        all_successful = True

        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            chunk = embeds[i:i + MAX_EMBEDS_PER_MESSAGE]
            chunk_num = (i // MAX_EMBEDS_PER_MESSAGE) + 1
            total_chunks = (len(embeds) + MAX_EMBEDS_PER_MESSAGE - 1) // MAX_EMBEDS_PER_MESSAGE

            # Create content message
            if total_chunks > 1:
                content = f"📢 **Earnings Date Notification** ({chunk_num}/{total_chunks}) - Total {total_stocks} stocks"
            else:
                content = f"📢 **Earnings Date Notification** - Earnings approaching for {total_stocks} stocks"

            # Send this chunk
            success = self.send_message(content, chunk)
            if not success:
                all_successful = False
                print(f"Warning: Failed to send notification chunk {chunk_num}/{total_chunks}")

        return all_successful

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

        # Sort stocks by price_change_rate:
        # 1. Positive changes (descending by absolute value)
        # 2. Negative changes (descending by absolute value)
        positive_changes = [s for s in stocks if s.get('price_change_rate', 0) > 0]
        negative_changes = [s for s in stocks if s.get('price_change_rate', 0) < 0]

        # Sort by absolute value in descending order
        positive_changes.sort(key=lambda s: abs(s.get('price_change_rate', 0)), reverse=True)
        negative_changes.sort(key=lambda s: abs(s.get('price_change_rate', 0)), reverse=True)

        # Combine: positive first, then negative
        sorted_stocks = positive_changes + negative_changes

        # Create embedded messages
        embeds = []

        for stock in sorted_stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            prev_price = stock.get('prev_price')
            price_change_rate = stock.get('price_change_rate')
            dividend = stock.get('dividend')
            dividend_yield = stock.get('dividend_yield')
            eps = stock.get('eps')
            per = stock.get('per')
            ma25 = stock.get('ma25')
            ma75 = stock.get('ma75')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if price_change_rate is None:
                continue

            # Determine color based on price change direction
            if price_change_rate > 0:
                color = 0x00FF00  # Green for positive change
                emoji = "📈"
            else:
                color = 0xFF0000  # Red for negative change
                emoji = "📉"

            # Create embedded fields
            fields = []

            # Add stock price information
            if price:
                price_text = f"{currency}{price:,.0f}"
                if price_change_rate is not None:
                    price_text += f" ({price_change_rate:+.2f}%)"
                fields.append({"name": "Current Price", "value": price_text, "inline": True})

            # Add PER information if available
            if per:
                fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})

            # Add dividend information if available
            if dividend_yield:
                fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})

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

        # Discord API limitation: max 10 embeds per message
        # Split embeds into chunks of 10 and send multiple messages if needed
        MAX_EMBEDS_PER_MESSAGE = 10
        total_stocks = len(embeds)
        all_successful = True

        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            chunk = embeds[i:i + MAX_EMBEDS_PER_MESSAGE]
            chunk_num = (i // MAX_EMBEDS_PER_MESSAGE) + 1
            total_chunks = (len(embeds) + MAX_EMBEDS_PER_MESSAGE - 1) // MAX_EMBEDS_PER_MESSAGE

            # Create content message
            if total_chunks > 1:
                content = f"💹 **Price Change Alert** ({chunk_num}/{total_chunks}) - Total {total_stocks} stocks"
            else:
                content = f"💹 **Price Change Alert** - Significant price changes detected for {total_stocks} stocks"

            # Send this chunk
            success = self.send_message(content, chunk)
            if not success:
                all_successful = False
                print(f"Warning: Failed to send price change notification chunk {chunk_num}/{total_chunks}")

        return all_successful

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

        # Create embedded messages
        embeds = []

        for stock in stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            ma25 = stock.get('ma25')
            ma75 = stock.get('ma75')
            prev_ma25 = stock.get('prev_ma25')
            prev_ma75 = stock.get('prev_ma75')
            cross_type = stock.get('cross_type')
            dividend = stock.get('dividend')
            dividend_yield = stock.get('dividend_yield')
            eps = stock.get('eps')
            per = stock.get('per')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not cross_type:
                continue

            # Determine color and message based on cross type
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

            # Create embedded fields
            fields = [
                {"name": "Signal Type", "value": cross_desc, "inline": False}
            ]

            # Add stock price information if available
            if price:
                price_text = f"{currency}{price:,.0f}"
                if price_change_rate is not None:
                    price_text += f" ({price_change_rate:+.2f}%)"
                fields.append({"name": "Current Price", "value": price_text, "inline": True})

            # Add PER information if available
            if per:
                fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})

            # Add dividend information if available
            if dividend_yield:
                fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})

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

        # Discord API limitation: max 10 embeds per message
        # Split embeds into chunks of 10 and send multiple messages if needed
        MAX_EMBEDS_PER_MESSAGE = 10
        total_stocks = len(embeds)
        all_successful = True

        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            chunk = embeds[i:i + MAX_EMBEDS_PER_MESSAGE]
            chunk_num = (i // MAX_EMBEDS_PER_MESSAGE) + 1
            total_chunks = (len(embeds) + MAX_EMBEDS_PER_MESSAGE - 1) // MAX_EMBEDS_PER_MESSAGE

            # Create content message
            if total_chunks > 1:
                content = f"📊 **Moving Average Cross Alert** ({chunk_num}/{total_chunks}) - Total {total_stocks} stocks"
            else:
                content = f"📊 **Moving Average Cross Alert** - MA cross detected for {total_stocks} stocks"

            # Send this chunk
            success = self.send_message(content, chunk)
            if not success:
                all_successful = False
                print(f"Warning: Failed to send MA cross notification chunk {chunk_num}/{total_chunks}")

        return all_successful

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

        # Create embedded messages
        embeds = []

        for stock in stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            ma25 = stock.get('ma25')
            ma75 = stock.get('ma75')
            dividend = stock.get('dividend')
            dividend_yield = stock.get('dividend_yield')
            eps = stock.get('eps')
            per = stock.get('per')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            if not (ma25 and ma75 and price):
                continue

            # Cyan color for pullback opportunity
            color = 0x00CED1  # DarkTurquoise
            emoji = "🎯"

            # Create embedded fields
            fields = [
                {"name": "Signal Type", "value": "Pullback Opportunity (MA25 > MA75, Price < MA75)", "inline": False}
            ]

            # Add stock price information
            price_text = f"{currency}{price:,.0f}"
            if price_change_rate is not None:
                price_text += f" ({price_change_rate:+.2f}%)"
            fields.append({"name": "Current Price", "value": price_text, "inline": True})

            # Add PER information if available
            if per:
                fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})

            # Add dividend information if available
            if dividend_yield:
                fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})

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

        # Discord API limitation: max 10 embeds per message
        # Split embeds into chunks of 10 and send multiple messages if needed
        MAX_EMBEDS_PER_MESSAGE = 10
        total_stocks = len(embeds)
        all_successful = True

        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            chunk = embeds[i:i + MAX_EMBEDS_PER_MESSAGE]
            chunk_num = (i // MAX_EMBEDS_PER_MESSAGE) + 1
            total_chunks = (len(embeds) + MAX_EMBEDS_PER_MESSAGE - 1) // MAX_EMBEDS_PER_MESSAGE

            # Create content message
            if total_chunks > 1:
                content = f"🎯 **Pullback Opportunity Alert** ({chunk_num}/{total_chunks}) - Total {total_stocks} stocks"
            else:
                content = f"🎯 **Pullback Opportunity Alert** - Potential buying opportunities for {total_stocks} stocks"

            # Send this chunk
            success = self.send_message(content, chunk)
            if not success:
                all_successful = False
                print(f"Warning: Failed to send pullback notification chunk {chunk_num}/{total_chunks}")

        return all_successful

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

        # Separate high and low breakouts
        high_breakouts = [s for s in stocks if s.get('high_breakout')]
        low_breakouts = [s for s in stocks if s.get('low_breakout')]

        # Sort by breakout period (longest first)
        high_breakouts.sort(key=lambda s: s.get('high_breakout', 0), reverse=True)
        low_breakouts.sort(key=lambda s: s.get('low_breakout', 0), reverse=True)

        # Combine: high breakouts first, then low breakouts
        sorted_stocks = high_breakouts + low_breakouts

        # Create embedded messages
        embeds = []

        for stock in sorted_stocks:
            code = stock.get('code')
            name = stock.get('name', '')
            price = stock.get('price')
            price_change_rate = stock.get('price_change_rate')
            high_breakout = stock.get('high_breakout')
            low_breakout = stock.get('low_breakout')
            dividend_yield = stock.get('dividend_yield')
            per = stock.get('per')
            market = stock.get('market', 'jp')
            currency = self._get_currency_symbol(market)

            # Determine breakout type and color
            if high_breakout and low_breakout:
                # Both high and low breakout
                color = 0xFFD700  # Gold
                emoji = "⚡"
                breakout_type = "High & Low Breakout"
                breakout_desc = f"High: {high_breakout} days, Low: {low_breakout} days"
            elif high_breakout:
                # High breakout only
                color = 0x00FF00  # Green
                emoji = "🚀"
                breakout_type = "High Breakout"
                breakout_desc = f"{high_breakout}-day high"
            else:
                # Low breakout only
                color = 0xFF0000  # Red
                emoji = "📉"
                breakout_type = "Low Breakout"
                breakout_desc = f"{low_breakout}-day low"

            # Create embedded fields
            fields = [
                {"name": "Breakout Type", "value": breakout_desc, "inline": False}
            ]

            # Add stock price information if available
            if price:
                price_text = f"{currency}{price:,.0f}"
                if price_change_rate is not None:
                    price_text += f" ({price_change_rate:+.2f}%)"
                fields.append({"name": "Current Price", "value": price_text, "inline": True})

            # Add PER information if available
            if per:
                fields.append({"name": "PER", "value": f"{per:.2f}", "inline": True})

            # Add dividend information if available
            if dividend_yield:
                fields.append({"name": "Dividend Yield", "value": f"{dividend_yield:.2f}%", "inline": True})

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

        # Discord API limitation: max 10 embeds per message
        # Split embeds into chunks of 10 and send multiple messages if needed
        MAX_EMBEDS_PER_MESSAGE = 10
        total_stocks = len(embeds)
        all_successful = True

        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            chunk = embeds[i:i + MAX_EMBEDS_PER_MESSAGE]
            chunk_num = (i // MAX_EMBEDS_PER_MESSAGE) + 1
            total_chunks = (len(embeds) + MAX_EMBEDS_PER_MESSAGE - 1) // MAX_EMBEDS_PER_MESSAGE

            # Create content message
            if total_chunks > 1:
                content = f"🔔 **Price Breakout Alert** ({chunk_num}/{total_chunks}) - Total {total_stocks} stocks"
            else:
                content = f"🔔 **Price Breakout Alert** - Breakouts detected for {total_stocks} stocks"

            # Send this chunk
            success = self.send_message(content, chunk)
            if not success:
                all_successful = False
                print(f"Warning: Failed to send breakout notification chunk {chunk_num}/{total_chunks}")

        return all_successful

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
        is_valid, message = Config.validate_config()
        return is_valid, message or "Discord configuration is correct"
