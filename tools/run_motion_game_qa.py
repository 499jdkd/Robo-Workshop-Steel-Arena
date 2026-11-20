"""Exercise the actual game with a synthetic MemoryStore and no ad requests."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.getenv("CLICKER_QA_SOURCE", str(ROOT / "src")))
sys.path.insert(0, str(SOURCE))

import flet as ft
import main as game
from battle_ui import animate_turn
from game_session import GameSession
from gameplay import GameState
from robot_catalog import ROBOTS


async def main(page):
    page.title = "Clicker · проверка игровых анимаций"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    session = GameSession.preview(page)
    session.motion_sound = False
    session.state = GameState(
        level=20,
        coin=20000,
        food=300,
        robot_levels={r.id: 5 for r in ROBOTS},
        active_robot="spark",
        egg_id="",
        robot_energy={r.id: 100 for r in ROBOTS},
        last_active_at=session.clock(),
    )
    mode = os.getenv("CLICKER_QA_MODE", "battle")
    if mode != "battle":
        session.state.work_id = "lamp"
        session.state.work_started_at = session.clock()
        session.state.work_end_at = session.clock() + 25
        session.state.work_reward = 30
        session.start()
        if mode in {'season','factory','store'}:session.route=mode
        if mode=='robot':session.robot_detail='spark'
    else:
        session.focus_scene = "battle"
        session.arena_expanded = True
        session.act("battle_start", "spark")
    with patch.object(game, "BannerFooter", lambda **_: ft.Container(height=0)):
        page.render(game.App, page=page, device_id="qa-synthetic", session=session,start_tab=1 if mode in {'collection','robot'} else 0)
    page.on_resize = lambda _: session.notify()

    async def scenario():
        await asyncio.sleep(2)
        sequence = ["attack", "guard", "special", "dodge", "charge"]
        index = 0
        while session.ui_alive:
            battle = session.state.battle
            if battle.get("result") != "active":
                robot = ROBOTS[(index // 5) % len(ROBOTS)].id
                session.act("battle_leave")
                session.state.robot_energy[robot] = 100
                session.act("battle_start", robot)
                battle = session.state.battle
            action = sequence[index % len(sequence)]
            if action == "special" and (
                battle.get("cooldown") or battle.get("focus", 2) < 2
            ):
                action = "charge"
            if action == "dodge" and (
                battle.get("dodge_cooldown") or battle.get("focus", 2) < 1
            ):
                action = "guard"
            await animate_turn(session, action, battle["id"], battle["turn"])
            index += 1
            await asyncio.sleep(0.12)

    if mode == "battle":
        page.run_task(scenario)
    page.on_disconnect = lambda _: session.pause()


if __name__ == "__main__":
    import os
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18552)
    args = parser.parse_args()
    os.environ["FLET_FORCE_WEB_SERVER"] = "1"
    ft.run(
        main,
        view=None,
        host="127.0.0.1",
        port=args.port,
        assets_dir=str(SOURCE / "assets"),
    )
