"""Export synthetic game screens for the real Flutter widget/layout checks."""

import asyncio
import base64
import json
import math
import sys
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
from flet.components.component import Renderer
from flet.controls.context import _context_page
from flet.messaging.protocol import configure_encode_object_for_msgpack

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]

from test_robot_ui import render_controls

import main
from game_session import GameSession
from gameplay import GameState

OUT = ROOT / ".cache/ui-fixtures"
ENCODE = configure_encode_object_for_msgpack(ft.BaseControl)


def to_wire(value):
    if isinstance(value, dict):
        if value.get("_c") == "GameRive":
            value["src"] = (ROOT / "src/assets/animation/game_robot.riv").as_posix()
            value["renderer"] = "flutter"
            payload = json.loads(value["payload"])
            payload["sound"] = False
            value["payload"] = json.dumps(payload)
        return {
            str(key.value if isinstance(key, Enum) else key): to_wire(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_wire(item) for item in value]
    if is_dataclass(value) or isinstance(value, Enum):
        return to_wire(ENCODE(value))
    return value


def portable(value):
    if isinstance(value, float) and not math.isfinite(value):
        return 1e9  # JSON has no infinity; a loose SizedBox is parent-constrained.
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, dict):
        if isinstance(value.get("src"), str):
            source = ROOT / "src/assets" / value["src"]
            if source.is_file() and value.get("_c") != "GameRive":
                value["src"] = base64.b64encode(source.read_bytes()).decode()
        return {key: portable(item) for key, item in value.items()}
    return value


async def fixture(
    name, tab, width, height, *, battle=False, expanded=False, phase=None,
    robot_id="spark", weapon=None, action="special",route='',detail='', energy=None
):
    page = SimpleNamespace(
        web=False,
        platform=ft.PagePlatform.ANDROID,
        width=width,
        height=height,
        run_task=Mock(),
        _dialogs=SimpleNamespace(controls=[]),
        session=SimpleNamespace(components_mode=True),
    )
    session = GameSession.preview(page)
    session.clock = lambda: 1008
    session.state = GameState(
        level=6,
        coin=370,
        experience=170,
        food=35,
        robot_levels={"spark": 3, "volt": 2, "flora": 1},
        active_robot="spark",
        egg_id="",
        arena_stage=3,
        last_active_at=1000,
        play_seconds=315,
        jobs_done=3,
        craft_counts={"lamp": 2, "robot": 1},
        parts=26,
    )
    session.arena_expanded = expanded
    if route or detail:
        from collection_progress import refresh_season
        session.state.coin=50000
        session.state.collection['modules']={'alloy':2,'reactor':1,'servo':2,'barrier':1,'scope':1}
        session.state.collection['module_loadouts']={'spark':{'armor':'alloy','core':'reactor','drive':'servo','defense':'barrier','gadget':'scope'}}
        session.state.collection['chests']={'normal':5,'rare':1}
        session.state.collection['skins']=['steel-1']
        session.state.weapon_levels={'plasma':3,'shield':2}
        session.state.loadouts={'spark':['plasma','shield']}
        refresh_season(session.state,session.clock())['xp']=1600
    if name.startswith('armory'):
        session.state.level=20
        session.state.coin=20000
        session.state.rare_parts=50
        session.state.weapon_levels={'plasma':3,'shield':2}
        session.state.loadouts={'spark':['plasma','shield']}
    if name.startswith('online-active') or name.startswith('clans-active'):
        import tempfile
        from server.arena_service import ArenaService
        from online_arena import online_for
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            service=ArenaService(Path(directory)/'arena.sqlite')
            first=service.register('Тестовый инженер А')
            second=service.register('Тестовый инженер Б')
            service.clan_action(first['id'],'create','Мастера')
            service.clan_action(second['id'],'create','Искры')
            service.enqueue(first['id'],'spark','plasma')
            service.enqueue(second['id'],'volt','electric')
            online=online_for(session)
            online.profile=service.profile(first['id'])
            online.match=service.current(first['id'])
            online.ranking=service.ranking()
            online.clans=service.clans(first['id'])
    session.state.robot_levels[robot_id] = 3
    session.state.active_robot = robot_id
    if weapon:
        session.state.weapon_levels[weapon] = 2
        session.state.loadouts[robot_id] = [weapon]
    session.focus_scene = "battle" if expanded else ""
    if name.startswith(("workshop-landscape", "motion-robot", "motion-emotion")):
        session.focus_scene = "workshop"
    if name.startswith("interaction-inspect"):
        session.focus_scene = "robot"
        session.inspection_id = robot_id
    if name.startswith("motion-emotion-"):
        session.motion_action = name.removeprefix("motion-emotion-")
        session.motion_event = 1
    if name == "workshop-landscape-siren":
        session.clock = lambda: 1053
    if name == "workshop-feeding":
        session.act("feed", "spark")
    if name == "incubator":
        session.state.level, session.state.coin = 8, 1000
        session.act("incubate", "glacier")
    if name == "profile-green":
        session.state.accent = "#36A58E"
    if name.startswith("reward-"):
        from rewarded_ads import RewardState, get_reward_controller

        controller = get_reward_controller(page, session)
        controller.state = reward_fixture_state = RewardState(
            phase="error" if name == "reward-error" else "loading",
            message="Сейчас нет подходящего видео. Попробуй позже"
            if name == "reward-error"
            else "Готовим видео…",
            offer_title="Искра: +30 опыта",
            attempts=1,
            error="stage: load\ncode: 3\ndomain: com.google.android.gms.ads\nmessage: No fill"
            if name == "reward-error"
            else "",
        )
    if battle:
        session.act("battle_start", robot_id)
        if energy is not None:
            session.state.battle["combatants"]["a"].update(energy=energy, super_charge=100)
            session.state.battle.update(battery=energy, super_charge=100)
        if phase:
            before = session.state.battle.copy()
            if phase not in {"approach", "flight"}:
                session.act("battle_turn", action, before["id"], 0)
            session.arena_animating = True
            session.arena_visual = dict(
                battle_id=before["id"],
                phase=phase,
                action=action,
                before_hp=before["player_hp"],
                before_enemy_hp=before["enemy_hp"],
            )
    token = _context_page.set(page)
    try:
        footer = ft.SafeArea(
            ft.Container(
                ft.Container(
                    ft.Text("AdMob · 320 × 50", color="#7B8799", size=11),
                    width=320,
                    height=50,
                    bgcolor="#EDF0F7",
                    alignment=ft.Alignment.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.only(top=8),
            ),
            avoid_intrusions_top=False,
        )
        with patch.object(main, "BannerFooter", return_value=footer):
            tree = Renderer().render(main.App, page=page, session=session)
            controls = render_controls(tree)
            if tab:
                nav = next(
                    control
                    for control in controls
                    if isinstance(control, ft.NavigationBar)
                )
                await nav.on_change(
                    SimpleNamespace(control=SimpleNamespace(selected_index=tab))
                )
                render_controls(tree)
            if route or detail:
                session.route=route;session.robot_detail=detail;session.notify()
                render_controls(tree)
            tree = tree._b
            if name.startswith('armory'):
                toggle=next(item for item in render_controls(tree) if item.key=='armory-tab')
                await toggle.on_click(None)
                render_controls(tree)
            if name.startswith(('online-','clans-')):
                target='clans-tab' if name.startswith('clans-') else 'pvp-tab'
                toggle=next(item for item in render_controls(tree) if item.key==target)
                await toggle.on_click(None)
                render_controls(tree)
            if name.startswith(("collection-boxes", "reward-")):
                boxes = next(
                    control
                    for control in render_controls(tree)
                    if isinstance(control, ft.Button) and control.content == "Боксы"
                )
                await boxes.on_click(None)
                if name.startswith("reward-"):
                    controller.state = reward_fixture_state
            if name == "reward-error":
                from rewarded_ads import RewardPanel

                panel = Renderer().render(RewardPanel, page=page, session=session)
                details = next(
                    control
                    for control in render_controls(panel)
                    if control.key == "reward-details"
                )
                await details.on_click(None)
                tree = ft.Container(
                    ft.Column([panel], scroll=ft.ScrollMode.AUTO, expand=True),
                    padding=14,
                )
            if name == "profile-icons":
                toggle = next(
                    control
                    for control in render_controls(tree)
                    if control.key == "profile-icons-toggle"
                )
                await toggle.on_click(None)
            if name.startswith("interaction-factory-"):
                from collection_progress import CHESTS
                kind = name.removeprefix("interaction-factory-")
                if kind == "rewards":
                    session.act("factory_open", "normal", 1)
                    render_controls(tree)
                    control = next(c for c in render_controls(tree) if c.key == "factory-show-rewards")
                    await control.on_click(None)
                    render_controls(tree)
                else:
                    label = CHESTS[kind][0].replace("Контейнер ", "").replace(" контейнер", "")
                    control = next(c for c in render_controls(tree) if isinstance(c, ft.Button) and c.content == label)
                    control.on_click(None)
                    render_controls(tree)
            if name == "arena-help":
                from arena_screen import BattleHelp

                dialogs = []
                with patch.object(ft, "use_dialog", side_effect=dialogs.append):
                    help_tree = Renderer().render(BattleHelp, session=session)
                    help_button = next(
                        item
                        for item in render_controls(help_tree)
                        if item.key == "arena-help"
                    )
                    await help_button.on_click(None)
                    render_controls(help_tree)
                    dialogs[-1].open = True
                    tree = ft.Container(dialogs[-1], alignment=ft.Alignment.CENTER)
            if name.startswith("robot-card-"):
                from robot_catalog import ROBOT_BY_ID
                from robot_ui import robot_card

                identity = name.removeprefix("robot-card-")
                session.state.robot_levels[identity] = 1
                tree = ft.Container(
                    ft.Column(
                        [robot_card(session, ROBOT_BY_ID[identity])],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    padding=14,
                )
            if name == "projects":
                from gameplay import start_order
                from main_screen import order_panel
                from progression_ui import project_gallery

                start_order(session.state, "lamp", 1000)
                tree = ft.Container(
                    ft.Column(
                        [
                            order_panel(session, session.clock()),
                            project_gallery(session),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=14,
                )
            if name == "supplies":
                from progression_ui import stored_eggs_panel, supplies_panel

                session.state.egg_stock = {"glacier": 1}
                tree = ft.Container(
                    ft.Column(
                        [supplies_panel(session), stored_eggs_panel(session)],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=14,
                )
            for control in render_controls(tree):
                control.before_update()
            encoded = to_wire(tree)
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{name}.json").write_text(
                json.dumps(portable(encoded), ensure_ascii=False), encoding="utf-8"
            )
    finally:
        _context_page.reset(token)


async def main_export():
    for kind in ("normal", "rare", "weapon", "parts", "capsule", "rewards"):
        await fixture("interaction-factory-"+kind,0,390,844,route="factory")
    for width, height, suffix in [(320,640,"-small"),(390,844,""),(844,390,"-landscape")]:
        await fixture("interaction-energy"+suffix,2,width,height,battle=True,robot_id="volt",energy=1)
        await fixture("interaction-zero"+suffix,2,width,height,battle=True,robot_id="volt",energy=0)
        await fixture("interaction-locked"+suffix,1,width,height,detail="titan")
        await fixture("interaction-inspect"+suffix,1,width,height,robot_id="arachna")
    for route in ('season','factory','store'):
        for suffix,width,height in [('',390,844),('-small',320,640),('-landscape',844,390)]:
            await fixture('feature-'+route+suffix,0,width,height,route=route)
    for suffix,width,height in [('',390,844),('-small',320,640),('-landscape',844,390)]:
        await fixture('feature-robot-detail'+suffix,1,width,height,detail='spark')
    for name, tab in (
        ("workshop-idle", 0),
        ("workshop-feeding", 0),
        ("collection", 1),
        ("arena-lobby", 2),
        ("profile-green", 3),
    ):
        await fixture(name, tab, 390, 844)
    await fixture("arena-portrait", 2, 390, 844, battle=True)
    await fixture("arena-small", 2, 320, 640, battle=True)
    await fixture("arena-landscape", 2, 844, 390, battle=True, expanded=True)
    await fixture(
        "arena-impact", 2, 844, 390, battle=True, expanded=True, phase="impact"
    )
    await fixture("arena-reply", 2, 844, 390, battle=True, expanded=True, phase="reply")
    await fixture(
        "arena-flight", 2, 844, 390, battle=True, expanded=True, phase="flight"
    )
    await fixture("workshop-landscape", 0, 844, 390)
    await fixture("workshop-landscape-siren", 0, 844, 390)
    await fixture("profile-icons", 3, 390, 844)
    await fixture("collection-boxes", 1, 390, 844)
    await fixture("collection-boxes-small", 1, 320, 640)
    await fixture("incubator", 1, 390, 844)
    await fixture("arena-help", 2, 844, 390, battle=True, expanded=True)
    await fixture("reward-loading", 1, 390, 844)
    await fixture("reward-loading-large-text", 1, 320, 640)
    await fixture("reward-error", 1, 390, 844)
    await fixture("projects", 0, 390, 844)
    await fixture("supplies", 0, 390, 844)
    for identity in ("glacier", "aegis", "solar"):
        await fixture("robot-card-" + identity, 0, 390, 650)
    from robot_catalog import ROBOTS
    from armory import WEAPONS

    for robot in ROBOTS:
        await fixture("motion-robot-" + robot.id, 0, 844, 390, robot_id=robot.id)
    for emotion in ("joy", "anger", "fear", "surprise", "victory", "defeat"):
        await fixture("motion-emotion-" + emotion, 0, 844, 390)
    for label,tab in [('armory',1),('online-offline',2),('online-active',2),('clans-offline',2),('clans-active',2)]:
        await fixture(label,tab,390,844)
        await fixture(label+'-small',tab,320,640)
    for weapon in WEAPONS:
        for phase in ("approach", "flight", "impact"):
            await fixture(f"motion-weapon-{weapon.id}-{phase}", 2, 844, 390,
                battle=True, expanded=True, phase=phase, weapon=weapon.id, action="attack")
    print("Exported", len(list(OUT.glob("*.json"))), "synthetic Flutter UI fixtures")


if __name__ == "__main__":
    asyncio.run(main_export())
