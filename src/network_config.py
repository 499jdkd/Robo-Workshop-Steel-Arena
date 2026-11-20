"""Release-owned endpoint; a player never has to enter infrastructure details."""

import json
import os
from app_paths import asset_path


def arena_url():
    configured = os.getenv("CLICKER_ARENA_URL", "")
    if not configured:
        try:
            configured = json.loads(
                asset_path("config/network.json").read_text(encoding="utf-8")
            ).get("arena_url", "")
        except (OSError, ValueError, AttributeError):
            return ""
    return str(configured).strip().rstrip("/")


def developer_network():
    return os.getenv("CLICKER_ARENA_DEVELOPER") == "1"
