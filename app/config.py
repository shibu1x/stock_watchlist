"""Configuration management module"""
import os
from typing import Optional


class Config:
    """Application configuration class"""

    # Database settings
    DB_PATH = os.getenv("DB_PATH", "data/stock_watchlist.db")

    # Discord settings
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Notification settings
    DEFAULT_NOTIFY_DAYS_BEFORE = int(os.getenv("DEFAULT_NOTIFY_DAYS_BEFORE", "3"))
    PRICE_CHANGE_THRESHOLD = float(os.getenv("PRICE_CHANGE_THRESHOLD", "5.0"))

    @classmethod
    def is_discord_configured(cls) -> bool:
        """
        Check if Discord configuration is complete

        Returns:
            True if configuration is complete
        """
        return bool(cls.DISCORD_WEBHOOK_URL)

    @classmethod
    def validate_config(cls) -> tuple[bool, Optional[str]]:
        """
        Check configuration validity

        Returns:
            (validity, error message)
        """
        if not cls.DISCORD_WEBHOOK_URL:
            return False, "DISCORD_WEBHOOK_URL is not set"

        return True, None
