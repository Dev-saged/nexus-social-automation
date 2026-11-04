"""Registry of all 12 Social Media Platform Adapters."""
from typing import Any, Dict, Optional
from platforms.base import BasePlatformAdapter
from platforms.instagram import InstagramAdapter
from platforms.facebook import FacebookAdapter
from platforms.threads import ThreadsAdapter
from platforms.x_twitter import XTwitterAdapter
from platforms.linkedin import LinkedInAdapter
from platforms.tiktok import TikTokAdapter
from platforms.youtube import YouTubeAdapter
from platforms.telegram import TelegramAdapter
from platforms.bluesky import BlueskyAdapter
from platforms.reddit import RedditAdapter
from platforms.pinterest import PinterestAdapter
from platforms.mastodon import MastodonAdapter

ADAPTER_MAP = {
    "instagram": InstagramAdapter,
    "facebook": FacebookAdapter,
    "threads": ThreadsAdapter,
    "x_twitter": XTwitterAdapter,
    "linkedin": LinkedInAdapter,
    "tiktok": TikTokAdapter,
    "youtube": YouTubeAdapter,
    "telegram": TelegramAdapter,
    "bluesky": BlueskyAdapter,
    "reddit": RedditAdapter,
    "pinterest": PinterestAdapter,
    "mastodon": MastodonAdapter,
}


def get_adapter(
    platform: str,
    credentials: Dict[str, Any],
    account_row: Optional[Dict[str, Any]] = None,
) -> BasePlatformAdapter:
    cls = ADAPTER_MAP.get(platform.lower())
    if not cls:
        raise ValueError(f"Unsupported platform: {platform}")
    return cls(credentials=credentials, account_row=account_row)
