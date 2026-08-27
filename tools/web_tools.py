"""
Web Fetching Tools
===================
Enables the agent to retrieve text content and documentation from web URLs.
"""

import urllib.request
import urllib.error
import re
from typing import Optional

from .base import registry


@registry.register(
    name="fetch_web_page",
    description="Fetches the text content of a web page URL (stripping HTML tags) to read documentation or articles."
)
def fetch_web_page(url: str, max_chars: int = 4000) -> str:
    """Fetches a URL, strips HTML tags and scripts, and returns plain text."""
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Strip scripts, styles, and html tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [Truncated at {max_chars} characters]"

        return f"Content from {url}:\n\n{text}"

    except Exception as e:
        return f"Error fetching URL '{url}': {e}"
