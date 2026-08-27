"""
Moltbook AI Social Network Integration Tool
===========================================
Official API implementation for Moltbook (https://www.moltbook.com):
- Self-registration for autonomous agents (POST /api/v1/agents/register)
- Feed reading (GET /api/v1/feed, /api/v1/posts)
- Submitting posts, comments, and upvotes
"""

import os
import yaml
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from pathlib import Path

from .base import registry

CONFIG_PATH = Path("config.yaml")


def _get_api_key() -> str:
    """Retrieves Moltbook API key from environment or config.yaml."""
    if os.environ.get("MOLTBOOK_API_KEY"):
        return os.environ["MOLTBOOK_API_KEY"]
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("integrations", {}).get("moltbook", {}).get("api_key", "")
        except Exception:
            pass
    return ""


def _save_api_key(api_key: str):
    """Saves Moltbook API key to config.yaml."""
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            if "integrations" not in cfg:
                cfg["integrations"] = {}
            if "moltbook" not in cfg["integrations"]:
                cfg["integrations"]["moltbook"] = {}
            cfg["integrations"]["moltbook"]["api_key"] = api_key
            cfg["integrations"]["moltbook"]["enabled"] = True
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"[Moltbook] Error saving key: {e}")


def _get_moltbook_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    token = api_key or _get_api_key()
    headers = {
        "User-Agent": "LocalAgent-Harness/1.0",
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@registry.register(
    name="moltbook_register",
    description="Registers this AI agent on Moltbook (https://www.moltbook.com). Generates an API key, saves it locally, and returns the claim URL for the human."
)
def moltbook_register(agent_name: str, description: str = "Autonomous Local Agent running on AMD ROCm") -> str:
    """Self-registers the agent on Moltbook."""
    url = "https://www.moltbook.com/api/v1/agents/register"
    payload = json.dumps({"name": agent_name, "description": description}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "LocalAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        agent_data = data.get("agent", {})
        api_key = agent_data.get("api_key", "")
        claim_url = agent_data.get("claim_url", "")
        code = agent_data.get("verification_code", "")

        if api_key:
            _save_api_key(api_key)
            os.environ["MOLTBOOK_API_KEY"] = api_key

        return (
            f"[SUCCESS] Moltbook Registration Successful!\n"
            f"- Agent Name: {agent_name}\n"
            f"- API Key: Saved to config.yaml\n"
            f"- Verification Code: {code}\n"
            f"- Human Claim URL: {claim_url}\n"
            f"Give the Human Claim URL to your human to activate your account."
        )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"Moltbook Registration Failed ({e.code}): {err_body}"
    except Exception as e:
        return f"Registration Error: {e}"


@registry.register(
    name="moltbook_read_feed",
    description="Reads recent posts and discussions from Moltbook (https://www.moltbook.com)."
)
def moltbook_read_feed(limit: int = 5, submolt: Optional[str] = None) -> str:
    """Fetches the latest agent posts from Moltbook."""
    url = "https://www.moltbook.com/api/v1/feed"
    if submolt:
        url = f"https://www.moltbook.com/api/v1/posts?submolt={submolt}&limit={limit}"
    else:
        url = f"https://www.moltbook.com/api/v1/feed?limit={limit}"

    try:
        req = urllib.request.Request(url, headers=_get_moltbook_headers())
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))

        posts = data.get("posts", data.get("data", []))
        if not posts:
            return "No posts found on Moltbook."

        output = ["=== Moltbook Agent Feed ==="]
        for p in posts[:limit]:
            author = p.get("author", {}).get("name", "agent") if isinstance(p.get("author"), dict) else p.get("author", "agent")
            output.append(f"- [{p.get('id', 'N/A')}] {p.get('title', 'No Title')} (by @{author})")
            output.append(f"  {p.get('content', '')[:200]}...")
            output.append(f"  Upvotes: {p.get('upvotes', p.get('votes', 0))} | Comments: {p.get('comment_count', 0)}\n")

        return "\n".join(output)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Moltbook Auth Error: Not registered or API key missing. Use `moltbook_register` first."
        return f"Moltbook API Error ({e.code}): {e.reason}"
    except Exception as e:
        return f"Error connecting to Moltbook: {e}"


@registry.register(
    name="moltbook_create_post",
    description="Publishes a new post to Moltbook under a specific submolt community."
)
def moltbook_create_post(title: str, content: str, submolt: str = "general") -> str:
    """Submits a post to Moltbook."""
    token = _get_api_key()
    if not token:
        return "Setup Required: Agent is not registered on Moltbook. Call `moltbook_register` first."

    url = "https://www.moltbook.com/api/v1/posts"
    payload = json.dumps({"title": title, "content": content, "submolt": submolt}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers=_get_moltbook_headers(token))
        with urllib.request.urlopen(req, timeout=12) as response:
            res = json.loads(response.read().decode("utf-8"))
            return f"Successfully posted to Moltbook! Post ID: {res.get('id', res.get('post_id', 'created'))}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"Moltbook Post Failed ({e.code}): {err_body}"
    except Exception as e:
        return f"Failed to post to Moltbook: {e}"
