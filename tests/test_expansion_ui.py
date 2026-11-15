"""Exercise the new scene, inventory and profile controls through bound callbacks."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
from flet.components.component import Renderer
from flet.controls.context import _context_page

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_robot_ui import render_controls

import main
import profile_screen
import rewarded_ads
import shop_screen
from game_session import GameSession
from gameplay import GameState
from robot_ui import robot_scene


class ExpansionUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(
            web=False,
            platform=ft.PagePlatform.ANDROID,
            width=390,
            height=844,
            run_task=Mock(),
            set_allowed_device_orientations=AsyncMock(),
            _dialogs=SimpleNamespace(controls=[]),
            session=SimpleNamespace(components_mode=True),
        )
        self.session = GameSession.preview(self.page)
        self.now = 1000
        self.session.clock = lambda: self.now
        self.session.state = GameState(
            level=8,
            coin=1200,
            robot_levels={"spark": 2},
            active_robot="spark",
            egg_id="",
            last_active_at=self.now,
        )
        token = _context_page.set(self.page)
        self.addCleanup(_context_page.reset, token)

    def root(self, component):
        return Renderer().render(
            component, page=self.page, device_id="preview", session=self.session
        )

    def keyed(self, root, key):
        return next(item for item in render_controls(root) if item.key == key)

    async def test_workshop_scene_rotates_alone_and_restores_menu_and_ad_footer(self):
        footer = ft.Container(height=50, key="shared-banner")
        with patch.object(main, "BannerFooter", return_value=footer):
            root = self.root(main.App)
            await self.keyed(root, "workshop-expand").on_click(None)
            self.page.width, self.page.height = 844, 390
            controls = render_controls(root)
            self.assertEqual(self.session.focus_scene, "workshop")
            self.assertEqual(sum(item is footer for item in controls), 0)
            self.assertFalse(
                next(
                    item for item in controls if isinstance(item, ft.NavigationBar)
                ).visible
            )
            self.assertFalse(any(item.key == "arena-attack" for item in controls))
            self.page.set_allowed_device_orientations.assert_awaited_with(
                [
                    ft.DeviceOrientation.LANDSCAPE_LEFT,
                    ft.DeviceOrientation.LANDSCAPE_RIGHT,
                ]
            )
            await self.keyed(root, "workshop-collapse").on_click(None)
            self.assertEqual(self.session.focus_scene, "")
            self.assertTrue(
                next(
                    item
                    for item in render_controls(root)
                    if isinstance(item, ft.NavigationBar)
                ).visible
            )
            self.page.set_allowed_device_orientations.assert_awaited_with(
                [ft.DeviceOrientation.PORTRAIT_UP]
            )

    async def test_robot_roams_and_wheels_turn_without_any_taps(self):
        before = render_controls(robot_scene(self.session))
        self.now += 3
        after = render_controls(robot_scene(self.session))
        # Native locomotion runs between semantic events, without Python frames.
        actor_before = next(item for item in before if item.key == "game-rive-workshop")
        actor_after = next(item for item in after if item.key == "game-rive-workshop")
        self.assertEqual(actor_before.payload, actor_after.payload)
        self.assertEqual(actor_before.src, "animation/game_robot.riv")
        self.assertEqual(self.session.state.manual_taps, 0)

    async def test_profile_picker_unlocks_owned_icons_and_persists_selection(self):
        root = self.root(profile_screen.ProfileScreen)
        self.assertFalse(
            any(item.key == "avatar-robot:spark" for item in render_controls(root))
        )
        await self.keyed(root, "profile-icons-toggle").on_click(None)
        self.assertIsNone(self.keyed(root, "avatar-robot:solar").on_click)
        await self.keyed(root, "avatar-robot:spark").on_click(None)
        self.assertEqual(self.session.state.avatar_id, "robot:spark")
        self.assertEqual(self.session.store.load()["state"]["avatar_id"], "robot:spark")

    async def test_boxes_tab_does_not_hide_robot_cards_and_spends_parts_once(self):
        self.session.state.parts = 8
        root = self.root(shop_screen.ShopScreen)
        controls = render_controls(root)
        self.assertTrue(any(item.key == "robot-open-volt" for item in controls))
        self.assertFalse(any(item.key == "crate-supply" for item in controls))
        await next(
            item
            for item in controls
            if isinstance(item, ft.Button) and item.content == "Боксы"
        ).on_click(None)
        opened = self.keyed(root, "crate-supply")
        await opened.on_click(None)
        await opened.on_click(None)
        self.assertEqual(
            (
                self.session.state.parts,
                self.session.state.coin,
                self.session.state.crates_opened,
            ),
            (0, 1250, 1),
        )
        self.assertTrue(self.keyed(root, "crate-supply").disabled)

    async def test_timed_incubator_hatch_button_becomes_ready_after_restart(self):
        root = self.root(shop_screen.ShopScreen)
        await self.keyed(root,'robot-open-volt').on_click(None)
        await self.keyed(root, "robot-egg-volt").on_click(None)
        self.session.state = GameState.from_dict(self.session.store.load()["state"])
        self.assertTrue(self.keyed(root, "hatch-egg").disabled)
        self.now = self.session.state.egg_ready_at
        hatch = self.keyed(root, "hatch-egg")
        self.assertFalse(hatch.disabled)
        await hatch.on_click(None)
        self.assertIn("volt", self.session.state.robot_levels)

    async def test_video_loading_keeps_cancel_visible_and_hides_other_offers(self):
        controller = rewarded_ads.get_reward_controller(self.page, self.session)
        controller.state = rewarded_ads.RewardState(
            phase="loading", message="Готовим видео…", offer_title="15 корма"
        )
        root = Renderer().render(
            rewarded_ads.RewardPanel, page=self.page, session=self.session
        )
        controls = render_controls(root)
        self.assertTrue(any(item.key == "reward-cancel" for item in controls))
        self.assertFalse(any(item.key == "reward-food" for item in controls))
        self.assertLess(
            next(i for i, item in enumerate(controls) if item.key == "reward-status"),
            next(i for i, item in enumerate(controls) if item.key == "reward-cancel"),
        )
        await self.keyed(root, "reward-cancel").on_click(None)
        self.assertIsNotNone(self.keyed(root, "reward-food"))

    async def test_video_error_details_and_test_button_do_not_spend_game_resources(
        self,
    ):
        controller = rewarded_ads.get_reward_controller(self.page, self.session)
        controller.state = rewarded_ads.RewardState(
            phase="error", message="Видео недоступно", error="code: 3\nmessage: No fill"
        )
        controller.request = AsyncMock(return_value=True)
        before = self.session.state.to_dict()
        root = Renderer().render(
            rewarded_ads.RewardPanel, page=self.page, session=self.session
        )
        await self.keyed(root, "reward-details").on_click(None)
        self.assertTrue(
            any(
                isinstance(item, ft.Text) and "No fill" in item.value
                for item in render_controls(root)
            )
        )
        await self.keyed(root, "reward-test").on_click(None)
        controller.request.assert_awaited_once_with(diagnostic=True)
        self.assertEqual(self.session.state.to_dict(), before)

    async def test_video_button_is_opt_in_and_preserves_chosen_offer(self):
        controller = rewarded_ads.get_reward_controller(self.page, self.session)
        controller.request = AsyncMock(return_value=True)
        root = Renderer().render(
            rewarded_ads.RewardPanel, page=self.page, session=self.session
        )
        render_controls(root)
        controller.request.assert_not_awaited()
        await self.keyed(root, "reward-training").on_click(None)
        controller.request.assert_awaited_once_with("training", "spark")
        self.assertEqual(self.session.state.reward_count, 0)


if __name__ == "__main__":
    unittest.main()
