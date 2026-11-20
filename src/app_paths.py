"""Asset paths for source, Android app archives and the Windows bundle."""

from pathlib import Path
import sys


def asset_path(relative):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return (
        root / ("game_assets" if getattr(sys, "frozen", False) else "assets") / relative
    )
