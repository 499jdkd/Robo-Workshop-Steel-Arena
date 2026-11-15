"""Headless Flet renderer + bound UI callbacks, without player files or network."""

import asyncio
import dataclasses
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
from flet.components.component import Component, Renderer
from flet.components.hooks.use_effect import EffectHook
from flet.controls.context import _context_page

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import arena_screen
import main
import main_screen
import profile_screen
import shop_screen
from game_session import GameSession
from gameplay import PALETTES, STAGES, GameState
from robot_arena import suggested_action
from robot_catalog import ROBOTS


def render_controls(root):
    visited = set()
    found = []

    def visit(value):
        if not dataclasses.is_dataclass(value) or id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, Component):
            value.before_update()
        if isinstance(value, ft.Control):
            found.append(value)
        for field in dataclasses.fields(value):
            if field.metadata.get("skip"):
                continue
            child = getattr(value, field.name)
            if isinstance(child, (list, tuple)):
                for item in child:
                    visit(item)
            elif isinstance(child, dict):
                for item in child.values():
                    visit(item)
            else:
                visit(child)

    visit(root)
    return found


class RobotUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(
            web=False,
            platform=ft.PagePlatform.WINDOWS,
            run_task=Mock(),
            _dialogs=SimpleNamespace(controls=[]),
            session=SimpleNamespace(components_mode=True),
        )
        self.session = GameSession.preview(self.page)
        self.now = 1000
        self.session.clock = lambda: self.now
        self.session.state.last_active_at = self.now
        token = _context_page.set(self.page)
        self.addCleanup(_context_page.reset, token)

    def root(self, component):
        return Renderer().render(
            component,
            page=self.page,
            device_id=self.session.device_id,
            session=self.session,
        )

    def keyed(self, root, key):
        return next(control for control in render_controls(root) if control.key == key)

    async def test_main_scene_taps_charge_then_open_first_robot(self):
        root = self.root(main_screen.MainScreen)
        for _ in range(12):
            await self.keyed(root, "robot-tap-scene").on_click(None)
        self.assertTrue(self.session.state.egg_ready)
        self.assertFalse(self.keyed(root, "hatch-egg").disabled)
        await self.keyed(root, "robot-tap-scene").on_click(None)
        self.assertEqual(self.session.state.robot_levels, {"spark": 1})
        self.assertGreater(self.session.reveal_until, self.now)
        images = [
            item.src for item in render_controls(root) if isinstance(item, ft.Image)
        ]
        self.assertIn("art/portraits/spark.svg", images)

    async def test_collection_buttons_buy_and_train_without_duplicate_charges(self):
        self.session.state = GameState(
            level=6,
            coin=1000,
            last_active_at=self.now,
            robot_levels={"spark": 1},
            active_robot="spark",
            egg_id="",
        )
        root = self.root(shop_screen.ShopScreen)
        await self.keyed(root,'robot-open-volt').on_click(None)
        buy = self.keyed(root, "robot-egg-volt")
        self.assertFalse(buy.disabled)
        await buy.on_click(None)
        await buy.on_click(None)
        self.assertEqual(
            (self.session.state.coin, self.session.state.egg_id), (820, "volt")
        )
        await self.keyed(root,'robot-detail-back').on_click(None)
        await self.keyed(root,'robot-open-spark').on_click(None)
        train = self.keyed(root, "train-spark")
        await train.on_click(None)
        self.assertEqual(
            (self.session.state.coin, self.session.state.robot_levels["spark"]),
            (760, 2),
        )

    async def test_classic_upgrades_tab_uses_real_hooks_and_controls(self):
        root = self.root(shop_screen.ShopScreen)
        tabs = [
            control
            for control in render_controls(root)
            if isinstance(control, ft.Button) and control.content == "Улучшения"
        ]
        self.assertEqual(len(tabs), 1)
        await tabs[0].on_click(None)
        controls = render_controls(root)
        upgrades = [
            control
            for control in controls
            if isinstance(control, ft.Button) and control.content == "Улучшить"
        ]
        self.assertEqual(len(upgrades), 4)

    async def test_screen_subscription_cleanup_survives_repeated_renders(self):
        root = self.root(main_screen.MainScreen)
        render_controls(root)
        effect = next(
            hook for hook in root._state.hooks if isinstance(hook, EffectHook)
        )
        effect.setup()
        self.assertEqual(len(self.session._listeners), 1)
        render_controls(root)
        effect.cleanup()
        self.assertEqual(self.session._listeners, [])

    async def test_workshop_click_feeds_selected_robot_automatically(self):
        self.session.state = GameState(
            food=4, robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        root = self.root(main_screen.MainScreen)
        await self.keyed(root, "robot-tap-scene").on_click(None)
        self.assertEqual((self.session.state.food, self.session.state.feedings), (1, 1))
        self.assertEqual(
            (
                self.session.state.robot_xp["spark"],
                self.session.state.robot_energy["spark"],
            ),
            (2, 88),
        )

    async def test_first_robot_and_arena_are_available_before_cloud_load(self):
        self.session.trusted = False
        self.session.act("tap", 12)
        root = self.root(main_screen.MainScreen)
        hatch = self.keyed(root, "hatch-egg")
        self.assertFalse(hatch.disabled)
        await hatch.on_click(None)
        battle_root = self.root(arena_screen.ArenaBattles)
        self.assertFalse(self.keyed(battle_root, "arena-start").disabled)
        await self.keyed(battle_root, "arena-start").on_click(None)
        self.assertEqual(self.session.state.battle["result"], "active")

    async def test_arena_start_and_bound_turn_buttons_complete_a_battle(self):
        self.session.state = GameState(
            robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        root = self.root(arena_screen.ArenaBattles)
        await self.keyed(root, "arena-start").on_click(None)
        reward = self.session.state.battle["reward"]
        first = self.keyed(root, "arena-attack")
        await first.on_click(None)
        await first.on_click(None)
        self.assertEqual(self.session.state.battle["turn"], 1)
        for _ in range(10):
            if self.session.state.battle["result"] != "active":
                break
            choice = suggested_action(self.session.state.battle)
            await self.keyed(root, f"arena-{choice}").on_click(None)
        self.assertEqual(
            (self.session.state.battle["result"], self.session.state.arena_wins),
            ("win", 1),
        )
        self.assertEqual(self.session.state.coin, reward)
        render_controls(root)

    async def test_arena_keeps_leaderboard_in_separate_tab(self):
        root = self.root(arena_screen.ArenaScreen)
        ranking = next(
            control
            for control in render_controls(root)
            if isinstance(control, ft.Button) and control.content == "Рейтинг"
        )
        await ranking.on_click(None)
        self.assertIsNotNone(self.keyed(root, "leaderboard-refresh"))

    async def test_all_worlds_and_selected_robots_have_packaged_image_sources(self):
        for stage in STAGES:
            for robot in ROBOTS:
                self.session.state = GameState(
                    level=stage.level,
                    robot_levels={robot.id: 1},
                    active_robot=robot.id,
                    egg_id="",
                )
                root = self.root(main_screen.MainScreen)
                images = [
                    control.src
                    for control in render_controls(root)
                    if isinstance(control, ft.Image)
                ]
                self.assertIn(robot.image, images)
                for source in images:
                    self.assertTrue((ROOT / "src/assets" / source).is_file(), source)
        images = [
            control.src
            for control in render_controls(self.root(profile_screen.ProfileScreen))
            if isinstance(control, ft.Image)
        ]
        self.assertTrue(
            all((ROOT / "src/assets" / source).is_file() for source in images)
        )

    async def test_fast_taps_keep_all_food_without_shrinking_or_restarting_the_pulse(
        self,
    ):
        self.session.state = GameState(
            robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        root = self.root(main_screen.MainScreen)
        handler = self.keyed(root, "robot-tap-scene").on_click
        tasks = [asyncio.create_task(handler(None)) for _ in range(80)]
        await asyncio.sleep(0)
        self.assertEqual(self.session.state.manual_taps, 80)
        self.assertEqual(self.session.state.food, 155)
        self.assertEqual(self.session.state.feedings, 1)
        for _ in range(3):
            controls = render_controls(root)
            actor = next(
                control for control in controls if control.key == "game-rive-workshop"
            )
            self.assertEqual(actor.src, "animation/game_robot.riv")
            self.assertIsNone(actor.scale)
            self.assertFalse(
                any(
                    isinstance(control, ft.AnimatedSwitcher)
                    and control.transition == ft.AnimatedSwitcherTransition.SCALE
                    for control in controls
                )
            )
        await asyncio.gather(*tasks)
        fountain = next(
            control
            for control in render_controls(root)
            if isinstance(control, ft.Container)
            and isinstance(control.content, ft.Text)
            and control.content.value == "+2 корма"
        )
        self.assertEqual(fountain.opacity, 0)
        self.assertEqual(self.session.state.manual_taps, 80)

    async def test_profile_color_changes_root_gradient_and_menu_and_survives_reload(
        self,
    ):
        self.page.update = Mock()
        profile = self.root(profile_screen.ProfileScreen)
        with patch.object(main, "BannerFooter", return_value=ft.Container(height=50)):
            before = self.root(main.App)
            render_controls(before)
            old_colors = list(before._b.controls[0].gradient.colors)
            await self.keyed(profile, "theme-1").on_click(None)
            after = self.root(main.App)
            render_controls(after)
        self.assertEqual(self.session.state.accent, PALETTES[1])
        self.assertNotEqual(after._b.controls[0].gradient.colors, old_colors)
        self.assertNotEqual(
            after._b.controls[1].indicator_color,
            before._b.controls[1].indicator_color,
        )
        restarted = GameSession(
            self.page, store=self.session.store, clock=self.session.clock
        )
        self.assertEqual(restarted.state.accent, PALETTES[1])

    async def test_expanded_arena_keeps_exactly_one_shared_ad_footer(self):
        self.page.window = SimpleNamespace(full_screen=False)
        self.page.update = Mock()
        self.session.state = GameState(
            robot_levels={"spark": 1}, active_robot="spark", egg_id=""
        )
        footer = ft.Container(height=50, key="test-shared-banner")
        with patch.object(main, "BannerFooter", return_value=footer) as factory:
            root = self.root(main.App)
            render_controls(root)
            nav = next(
                control
                for control in render_controls(root)
                if isinstance(control, ft.NavigationBar)
            )
            await nav.on_change(
                SimpleNamespace(control=SimpleNamespace(selected_index=2))
            )
            await self.keyed(root, "arena-start").on_click(None)
            await self.keyed(root, "arena-scene-expand").on_click(None)
            self.page.width, self.page.height = 900, 420
            controls = render_controls(root)
            self.assertFalse(self.page.window.full_screen)
            self.assertEqual(self.page.window.width, 960)
            self.assertTrue(self.session.arena_expanded)
            nav = next(
                control for control in controls if isinstance(control, ft.NavigationBar)
            )
            self.assertFalse(nav.visible)
            self.assertEqual(sum(control is footer for control in controls), 0)
            self.assertIsNotNone(self.keyed(root, "arena-dodge"))
            await self.keyed(root, "arena-scene-collapse").on_click(None)
            self.assertFalse(self.page.window.full_screen)
            self.assertTrue(
                next(
                    control
                    for control in render_controls(root)
                    if isinstance(control, ft.NavigationBar)
                ).visible
            )
        self.assertGreater(factory.call_count, 1)


if __name__ == "__main__":
    unittest.main()
