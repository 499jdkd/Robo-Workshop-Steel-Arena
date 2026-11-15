import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import flet_ads as ads
from flet.components.component import Renderer
from flet.components.hooks.use_effect import EffectHook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import advertising


def consent_manager(allowed=False):
    return SimpleNamespace(
        request_consent_info_update=AsyncMock(),
        load_and_show_consent_form_if_required=AsyncMock(),
        can_request_ads=AsyncMock(return_value=allowed),
        get_privacy_options_requirement_status=AsyncMock(
            return_value=ads.PrivacyOptionsRequirementStatus.NOT_REQUIRED
        ),
        show_privacy_options_form=AsyncMock(),
    )


def banner_control(controller):
    return next(
        control
        for control in advertising.banner_view(controller).content.content.controls
        if isinstance(control, ads.BannerAd)
    )


class AdRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID)
        self.now = 1000
        self.controllers = []
        logger = patch.object(advertising, "logger")
        logger.start()
        self.addCleanup(logger.stop)

    def controller(self, **kwargs):
        kwargs.setdefault("manager_factory", lambda: consent_manager(True))
        controller = advertising.AdController(
            self.page, clock=lambda: self.now, **kwargs
        )
        self.controllers.append(controller)
        return controller

    async def asyncTearDown(self):
        for controller in self.controllers:
            await controller.close()

    async def test_google_fixed_demo_unit_does_not_depend_on_publisher_consent_config(
        self,
    ):
        factory = Mock(
            side_effect=AssertionError("Demo must not require a publisher account")
        )
        controller = self.controller(
            unit_id=advertising.TEST_BANNER_UNIT_ID, manager_factory=factory
        )
        await controller.start()
        factory.assert_not_called()
        self.assertTrue(controller.state.allowed)
        banner = banner_control(controller)
        self.assertIsInstance(banner, ads.BannerAd)
        self.assertEqual(banner.unit_id, "ca-app-pub-3940256099942544/6300978111")
        self.assertEqual((banner.width, banner.height), (320, 50))
        self.assertTrue(banner.request.non_personalized_ads)
        await banner.on_load(None)
        self.assertEqual(controller.state.phase, "loaded")

    async def test_owner_unit_cannot_bypass_ump_denial(self):
        manager = consent_manager(False)
        controller = self.controller(
            unit_id="ca-app-pub-owner/real", manager_factory=lambda: manager
        )
        await controller.start()
        self.assertEqual(controller.state.phase, "blocked")
        self.assertFalse(controller.state.allowed)
        manager.request_consent_info_update.assert_awaited_once()
        params = manager.request_consent_info_update.await_args.args[0]
        self.assertTrue(params.tag_for_under_age_of_consent)
        self.assertFalse(
            any(
                isinstance(c, ads.BannerAd)
                for c in advertising.banner_view(controller).content.content.controls
            )
        )

    async def test_owner_unit_needs_valid_permission_even_after_update_error(self):
        manager = consent_manager(False)
        manager.request_consent_info_update.side_effect = RuntimeError(
            "no publisher message"
        )
        controller = self.controller(
            unit_id="ca-app-pub-3940256099942544/not-allowlisted",
            manager_factory=lambda: manager,
        )
        await controller.start()
        self.assertFalse(controller.demo)
        self.assertFalse(controller.state.allowed)

    async def test_owner_unit_with_ump_permission_can_load(self):
        manager = consent_manager(True)
        controller = self.controller(manager_factory=lambda: manager)
        await controller.start()
        self.assertFalse(controller.demo)
        manager.request_consent_info_update.assert_awaited_once()
        manager.can_request_ads.assert_awaited_once()
        self.assertTrue(controller.state.allowed)
        self.assertEqual(controller.state.phase, "loading")
        banner = banner_control(controller)
        self.assertEqual(banner.unit_id, advertising.BANNER_UNIT_ID)
        self.assertTrue(banner.request.non_personalized_ads)

    async def test_failed_banner_has_visible_status_and_manual_retry_replaces_it(self):
        controller = self.controller()
        await controller.start()
        first = banner_control(controller)
        await first.on_error(
            SimpleNamespace(data="LoadAdError(code: 2, network unavailable)")
        )
        self.assertEqual(controller.state.phase, "failed")
        controls = advertising.banner_view(controller).content.content.controls
        self.assertTrue(any(isinstance(c, ft.Row) for c in controls))
        self.assertFalse(any(isinstance(c, ads.BannerAd) for c in controls))
        self.assertFalse(await controller.retry())
        self.now += 30
        self.assertTrue(await controller.retry())
        second = banner_control(controller)
        self.assertNotEqual(first.key, second.key)
        await first.on_load(None)
        self.assertEqual(controller.state.phase, "loading")
        await second.on_load(None)
        self.assertEqual(controller.state.phase, "loaded")

    async def test_sdk_auto_refresh_failure_is_recoverable_after_initial_success(self):
        controller = self.controller()
        await controller.start()
        controller.loaded(controller.state.generation)
        controller.failed(controller.state.generation, "refresh network error")
        self.assertEqual(controller.state.phase, "failed")
        self.assertIsNotNone(controller._retry)

    async def test_load_deadline_and_auto_retry_are_bounded(self):
        waits = []

        async def wait(delay):
            event = asyncio.Event()
            waits.append((delay, event))
            await event.wait()

        controller = self.controller(sleep=wait)
        await controller.start()
        await asyncio.sleep(0)
        self.assertEqual(waits[0][0], advertising.LOAD_TIMEOUT)
        waits[0][1].set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(controller.state.phase, "failed")
        self.assertIn("25", controller.state.error)
        retry = controller._retry
        for delay, event in waits[1:]:
            if delay == 30:
                event.set()
        self.now += 30
        await retry
        self.assertEqual(
            (controller.state.phase, controller.state.attempts), ("loading", 2)
        )

    async def test_stale_errors_and_close_cannot_change_new_or_destroyed_view(self):
        controller = self.controller()
        await controller.start()
        listener = Mock()
        controller.subscribe(listener)
        before = controller.state
        await controller.close()
        controller.loaded(before.generation)
        controller.failed(before.generation, "late error")
        listener.assert_not_called()
        self.assertEqual(controller.state, before)
        self.assertEqual(controller._tasks, set())

    async def test_privacy_button_is_retained_when_ads_are_blocked(self):
        manager = consent_manager(False)
        manager.get_privacy_options_requirement_status.return_value = (
            ads.PrivacyOptionsRequirementStatus.REQUIRED
        )
        controller = self.controller(
            unit_id="owner/unit", manager_factory=lambda: manager
        )
        await controller.start()
        controls = advertising.banner_view(controller).content.content.controls
        privacy = next(c for c in controls if isinstance(c, ft.TextButton))
        await privacy.on_click(None)
        manager.show_privacy_options_form.assert_awaited_once()

    async def test_windows_shows_an_explicit_layout_preview_without_mobile_sdk(self):
        page = SimpleNamespace(web=False, platform=ft.PagePlatform.WINDOWS)
        for unit_id in (advertising.TEST_BANNER_UNIT_ID, advertising.BANNER_UNIT_ID):
            with (
                self.subTest(unit_id=unit_id),
                patch.object(advertising, "BANNER_UNIT_ID", unit_id),
                patch.object(ads, "BannerAd") as banner,
                patch.object(ads, "ConsentManager") as manager,
            ):
                result = advertising.BannerFooter.__wrapped__(page)
            banner.assert_not_called()
            manager.assert_not_called()
            self.assertEqual(result.content.controls[1].height, 50)
            self.assertIn(
                "Макет",
                result.content.controls[1].content.controls[1].controls[1].value,
            )

    async def test_web_and_ios_do_not_request_android_inventory(self):
        for page in (
            SimpleNamespace(web=True, platform=ft.PagePlatform.ANDROID),
            SimpleNamespace(web=False, platform=ft.PagePlatform.IOS),
        ):
            result = advertising.BannerFooter.__wrapped__(page)
            self.assertEqual(result.height, 0)

    async def test_footer_reconnect_cleanup_does_not_close_replacement_controller(self):
        original_controller = advertising.AdController

        def create_controller(page, **kwargs):
            kwargs["manager_factory"] = lambda: consent_manager(True)
            controller = original_controller(page, **kwargs)
            self.controllers.append(controller)
            return controller

        with patch.object(advertising, "AdController", side_effect=create_controller):
            root = Renderer().render(advertising.BannerFooter, page=self.page)
            root.before_update()
            first = advertising.get_ad_controller(self.page)
            effect = next(
                hook
                for hook in root._state.hooks
                if isinstance(hook, EffectHook) and hook.setup.__name__ == "boot"
            )
            effect.setup()
            await first.start()
            self.assertEqual(first.state.phase, "loading")
            await first.close()
            root.before_update()
            second = advertising.get_ad_controller(self.page)
            effect.cleanup()
            self.assertTrue(second.alive)
            effect.setup()
            await second.start()
            self.assertEqual(second.state.phase, "loading")


if __name__ == "__main__":
    unittest.main()
