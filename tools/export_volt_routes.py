"""Export the real App route shell with small body markers for transition QA."""

import asyncio
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]

import flet as ft
from flet.components.component import Renderer
from flet.controls.context import _context_page
from game_session import GameSession
from gameplay import GameState
import main
from test_robot_ui import render_controls
from tools.export_ui_fixtures import to_wire


def stable_ids(value):
    counter = 100

    def visit(node):
        nonlocal counter
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: visit(item) for key, item in node.items()}
        if "_c" in result:
            result["_i"] = counter
            counter += 1
        return result

    return visit(value)


def with_legacy_switcher(encoded):
    """Reproduce v32's exact 0 ms in / 1 s out transition for a red check."""
    host = encoded["controls"][0]
    destination = host.pop("key")
    padded = host["content"]["content"]
    padded["content"] = {
        "_c": "AnimatedSwitcher", "expand": True, "duration": 0,
        "reverse_duration": {"seconds": 1},
        "content": {"_c": "Container", "expand": True, "key": destination,
                    "content": padded["content"]},
    }
    return encoded


async def export(legacy=False):
    page = SimpleNamespace(
        width=390, height=844, web=True, run_task=Mock(),
        _dialogs=SimpleNamespace(controls=[]), session=SimpleNamespace(components_mode=True),
    )
    session = GameSession.preview(page)
    session.state = GameState(robot_levels={"volt": 4}, active_robot="volt", egg_id="")
    token = _context_page.set(page)
    labels = {0: "route-workshop", 1: "route-collection", 2: "route-arena", 3: "route-profile"}
    out = ROOT / f".cache/volt-refinement/qa/route-fixtures{'-before' if legacy else ''}"
    out.mkdir(parents=True, exist_ok=True)
    try:
        def marker(index):
            return lambda *args, **kwargs: ft.Container(
                ft.Text(labels[index], size=24), expand=True, bgcolor="#122B50")

        with patch.object(main, "main_screen", marker(0)), patch.object(main, "shop_screen", marker(1)), \
             patch.object(main, "arena_screen", marker(2)), patch.object(main, "profile_screen", marker(3)), \
             patch.object(main, "BannerFooter", lambda **kwargs: ft.Container(height=0)):
            root = Renderer().render(main.App, page=page, session=session, start_tab=3)
            for index in (3, 0, 1, 2):
                controls = render_controls(root)
                navigation = next(control for control in controls if control.key == "main-navigation")
                await navigation.on_change(SimpleNamespace(control=SimpleNamespace(selected_index=index)))
                render_controls(root)
                encoded = to_wire(root._b)
                if legacy:
                    encoded = with_legacy_switcher(encoded)
                encoded = stable_ids(encoded)
                (out / f"{labels[index]}.json").write_text(json.dumps(encoded, ensure_ascii=False), encoding="utf-8")
        print("Exported four real App route shells with synthetic body markers:", out)
    finally:
        _context_page.reset(token)
        await session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-switcher", action="store_true")
    asyncio.run(export(parser.parse_args().legacy_switcher))
