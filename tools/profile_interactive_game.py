"""Render the primary game with synthetic data and record native first-paint time.

Use --source with a saved source tree for a baseline. No real save, ad request,
leaderboard write or public matchmaking is involved.
"""

import argparse
import asyncio
import json
from importlib.metadata import version
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=ROOT / "src")
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--port", type=int, default=18557)
parser.add_argument("--mode", choices=("workshop", "battle", "robot"), default="workshop")
parser.add_argument("--robot", default="volt")
parser.add_argument("--silent", action="store_true")
parser.add_argument("--music-check", action="store_true", help="Exercise real main-game music with isolated data")
parser.add_argument("--showcase-action", choices=("attack", "quick", "special", "ultimate", "guard", "dodge", "charge"))
args = parser.parse_args()
if args.music_check:
    args.mode='robot'
args.out.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(args.source.resolve()), str(ROOT)]
import_started = time.perf_counter()

import flet as ft
import main as game
import robot_ui
from game_session import GameSession
from gameplay import GameState
from robot_arena import suggested_action
from battle_ui import animate_turn

(args.out / "python-import.json").write_text(json.dumps({
    "import_ms": (time.perf_counter()-import_started)*1000,
    "flet": version("flet"), "flet_module": ft.__file__,
    "main_source": game.__file__, "robot": args.robot,
}), encoding="utf-8")


async def main(page):
    created = time.perf_counter()
    page.title = "Robo Workshop · synthetic main-game check"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    session = GameSession.preview(page)
    session.demo = True
    session.motion_sound = not args.silent
    session.state = GameState(level=20, coin=20000, food=300,
                              robot_levels={args.robot: 5}, active_robot=args.robot,
                              egg_id="", robot_energy={args.robot: 100}, last_active_at=session.clock())
    original = robot_ui.animated_scene

    def instrumented(*pos, **kw):
        control = original(*pos, **kw)
        control.report_ready = True
        def ready(event):
            data = event.data if isinstance(event.data, dict) else json.loads(event.data) if event.data else {"robot":args.robot,"renderer":"baseline"}
            with (args.out / "first-paint.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({**data, "since_session_ms":(time.perf_counter()-created)*1000})+"\n")
        control.on_ready = ready
        return control

    robot_ui.animated_scene = instrumented
    if args.mode == "battle":
        import battle_ui
        battle_ui.animated_scene = instrumented
        session.focus_scene = "battle"
        session.act("battle_start", args.robot)
    if args.mode == "robot":
        import robot_preview
        robot_preview.animated_scene = instrumented
        session.robot_detail = args.robot
    with patch.object(game, "BannerFooter", lambda **_: ft.Container(height=0)):
        page.render(game.App, page=page, device_id="synthetic-profile-v27", session=session)
    (args.out / "first-render.json").write_text(json.dumps({"python_first_render_ms":(time.perf_counter()-created)*1000}), encoding="utf-8")
    page.on_resize = lambda _: session.notify()
    session.start()

    async def scenario():
        if args.music_check:
            def mark(name):
                with (args.out/'music-scenario.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps({'name':name,'since_session_ms':(time.perf_counter()-created)*1000})+'\n')
            await asyncio.sleep(3)
            mark('victory-1');session.preview_robot(args.robot,'victory')
            await asyncio.sleep(.8)
            mark('pulse-during-victory');session.preview_robot(args.robot,'attack')
            await asyncio.sleep(.6)
            mark('leave-inspection');session.robot_detail='';session.notify()
            await asyncio.sleep(3.7)
            mark('arena');session.act('battle_start',args.robot);session.focus_scene='battle';session.notify()
            await asyncio.sleep(1.4)
            mark('inspection');session.focus_scene='';session.robot_detail=args.robot;session.notify()
            await asyncio.sleep(.7)
            mark('victory-2');session.preview_robot(args.robot,'victory')
            await asyncio.sleep(1.6)
            mark('pause');session.pause()
            await asyncio.sleep(1)
            mark('resume');session.resume()
            for action in ['attack','special','quick']:
                session.preview_robot(args.robot,action);await asyncio.sleep(.15)
            await asyncio.sleep(5)
            mark('storm');session.preview_robot(args.robot,'ultimate')
            await asyncio.sleep(2.8)
            mark('complete')
        elif args.mode == "robot":
            while session.ui_alive:
                for action in ([args.showcase_action] if args.showcase_action else ("attack", "special", "ultimate", "guard")):
                    session.preview_robot(args.robot, action)
                    await asyncio.sleep(3.6 if args.robot == 'titan' and action == 'ultimate' else 2.8)
        elif args.mode == "battle":
            await asyncio.sleep(2)
            while session.ui_alive:
                battle = session.state.battle
                if battle.get("result") != "active":
                    session.act("battle_leave")
                    session.state.robot_energy[args.robot] = 100
                    session.act("battle_start", args.robot)
                    battle = session.state.battle
                await animate_turn(session, suggested_action(battle), battle["id"], battle["turn"])
                await asyncio.sleep(.15)
    if args.mode != "workshop":
        page.run_task(scenario)
    async def disconnected(_):
        await session.close()
    page.on_disconnect = disconnected
    async def connected(_):
        session.resume()
    page.on_connect = connected


if __name__ == "__main__":
    os.environ["FLET_FORCE_WEB_SERVER"] = "1"
    ft.run(main, view=None, host="127.0.0.1", port=args.port,
           assets_dir=str(args.source.resolve() / "assets"))
