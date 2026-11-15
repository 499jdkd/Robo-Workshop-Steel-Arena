"""Ad requests are mocked: no real ads or player data are sent by these tests."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import flet_ads as ads

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import advertising  # noqa: E402
import main  # noqa: E402


class ConsentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = Mock()
        for method in (
            "request_consent_info_update",
            "load_and_show_consent_form_if_required",
            "can_request_ads",
            "get_privacy_options_requirement_status",
        ):
            setattr(self.manager, method, AsyncMock())
        self.manager.can_request_ads.return_value = True
        self.manager.get_privacy_options_requirement_status.return_value = (
            ads.PrivacyOptionsRequirementStatus.NOT_REQUIRED
        )
        logger_patch = patch.object(advertising, "logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)

    async def test_consent_is_updated_before_ads_are_allowed(self):
        result = await advertising.refresh_consent(self.manager)
        self.assertTrue(result.can_request_ads)
        self.assertEqual(
            [call[0] for call in self.manager.mock_calls],
            [
                "request_consent_info_update",
                "load_and_show_consent_form_if_required",
                "can_request_ads",
                "get_privacy_options_requirement_status",
            ],
        )
        params = self.manager.request_consent_info_update.call_args.args[0]
        self.assertTrue(params.tag_for_under_age_of_consent)

    async def test_no_ad_permission_does_not_hide_required_privacy_options(self):
        self.manager.can_request_ads.return_value = False
        self.manager.get_privacy_options_requirement_status.return_value = (
            ads.PrivacyOptionsRequirementStatus.REQUIRED
        )
        result = await advertising.refresh_consent(self.manager)
        self.assertFalse(result.can_request_ads)
        self.assertTrue(result.privacy_options_required)

    async def test_network_error_can_use_a_valid_ump_decision(self):
        self.manager.request_consent_info_update.side_effect = RuntimeError("offline")
        result = await advertising.refresh_consent(self.manager)
        self.assertTrue(result.can_request_ads)
        self.manager.load_and_show_consent_form_if_required.assert_not_awaited()

    async def test_unavailable_ump_hides_ads_without_failing_startup(self):
        self.manager.request_consent_info_update.side_effect = RuntimeError("offline")
        self.manager.can_request_ads.side_effect = RuntimeError("SDK unavailable")
        result = await advertising.refresh_consent(self.manager)
        self.assertFalse(result.can_request_ads)
        self.assertIn("SDK unavailable", result.error)

    async def test_consent_form_error_does_not_override_ump_denial(self):
        self.manager.load_and_show_consent_form_if_required.side_effect = RuntimeError(
            "form"
        )
        self.manager.can_request_ads.return_value = False
        self.assertFalse(
            (await advertising.refresh_consent(self.manager)).can_request_ads
        )


class BannerFooterTests(unittest.TestCase):
    def setUp(self):
        self.page = SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID)

    def test_all_navigation_screens_share_one_footer(self):
        for index in range(4):
            with (
                self.subTest(index=index),
                patch.object(ft, "use_state", return_value=(index, Mock())),
                patch.object(main, "use_game", side_effect=lambda session: session.state),
            ):
                with (
                    patch.multiple(
                        main,
                        main_screen=Mock(return_value=ft.Container()),
                        shop_screen=Mock(return_value=ft.Container()),
                        arena_screen=Mock(return_value=ft.Container()),
                        profile_screen=Mock(return_value=ft.Container()),
                    ),
                    patch.object(
                        main, "BannerFooter", return_value=ft.Container(height=50)
                    ) as footer,
                ):
                    root = main.App.__wrapped__(self.page, "existing-device")
                footer.assert_called_once_with(page=self.page, key="advertising-footer")
                self.assertEqual(root.controls[0].expand, True)
                self.assertIsInstance(root.controls[1], ft.NavigationBar)
                self.assertEqual(root.controls[-1].height, 50)
                self.assertEqual(root.spacing, 0)


if __name__ == "__main__":
    unittest.main()
