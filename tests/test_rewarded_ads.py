"""No live ad requests: lifecycle events are delivered by a fake SDK."""

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import flet as ft
from flet.controls.context import _context_page

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import rewarded_ads
from game_session import GameSession
from rewarded_ads import RewardController


class RewardedControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID)
        self.session = GameSession.preview(self.page)
        self.session.clock = lambda: 1000
        self.service = SimpleNamespace(
            load=AsyncMock(),
            show=AsyncMock(),
            cancel=AsyncMock(),
            dispose_ad=AsyncMock(),
        )
        self.factory = Mock(return_value=self.service)
        self.controller = RewardController(
            self.page,
            self.session,
            unit_id=rewarded_ads.TEST_REWARDED_UNIT_ID,
            factory=self.factory,
        )

        async def immediate_load(token):
            await self.controller.loaded(self.event(token))

        self.service.load.side_effect = immediate_load

    def event(self, token=None):
        return SimpleNamespace(
            data={
                "request_id": token or self.controller.token,
                "amount": 1,
                "type": "reward",
            }
        )

    async def asyncTearDown(self):
        await self.controller.close()
        await self.session.close()

    async def test_loading_opening_and_closing_do_not_grant_a_reward(self):
        self.assertTrue(await self.controller.request("food"))
        await self.controller.opened(self.event())
        await self.controller.dismissed(self.event())
        self.assertEqual(
            (self.session.state.food, self.session.state.reward_count), (0, 0)
        )

    async def test_only_earned_callback_grants_once_and_persists(self):
        await self.controller.request("food")
        self.assertEqual(self.session.state.food, 0)
        await self.controller.earned(self.event())
        await self.controller.earned(self.event())
        await self.controller.dismissed(self.event())
        self.assertEqual(
            (self.session.state.food, self.session.state.reward_count), (15, 1)
        )
        self.assertEqual(self.session.store.load()["state"]["food"], 15)
        self.assertFalse(await self.controller.request("food"))

    async def test_stale_event_and_callback_after_disposal_are_ignored(self):
        await self.controller.request("food")
        await self.controller.earned(self.event("other-token"))
        await self.controller.close()
        await self.controller.earned(self.event())
        self.assertEqual(self.session.state.food, 0)

    async def test_loading_can_be_cancelled_and_late_load_never_shows(self):
        started = asyncio.Event()

        async def pending(token):
            started.set()

        self.service.load.side_effect = pending
        task = asyncio.create_task(self.controller.request("food"))
        await started.wait()
        token = self.controller.token
        await self.controller.cancel_pending()
        self.assertFalse(await task)
        await self.controller.loaded(self.event(token))
        self.service.show.assert_not_awaited()
        self.assertEqual(self.session.state.food, 0)

    async def test_simultaneous_buttons_do_not_start_two_videos(self):
        started = asyncio.Event()

        async def pending(token):
            started.set()

        self.service.load.side_effect = pending
        task = asyncio.create_task(self.controller.request("food"))
        await started.wait()
        self.assertFalse(await self.controller.request("boost"))
        self.factory.assert_called_once()
        await self.controller.cancel_pending()
        await task

    async def test_windows_never_initializes_the_mobile_ad_service(self):
        self.page.platform = ft.PagePlatform.WINDOWS
        self.assertFalse(await self.controller.request("food"))
        self.factory.assert_not_called()

    async def test_publisher_rewarded_unit_requires_real_ump_permission(self):
        self.controller.unit_id = "ca-app-pub-1234567890123456/1234567890"
        banner = SimpleNamespace(
            start=AsyncMock(),
            manager=SimpleNamespace(can_request_ads=AsyncMock(return_value=False)),
        )
        with patch.object(rewarded_ads, "get_ad_controller", return_value=banner):
            self.assertFalse(await self.controller.request("food"))
        self.factory.assert_not_called()
        self.assertEqual(self.session.state.reward_count, 0)

    async def test_actual_flet_event_dispatch_preserves_native_payload_and_rewards(
        self,
    ):
        context_token = _context_page.set(None)
        self.addCleanup(_context_page.reset, context_token)
        service = rewarded_ads.RewardedAd(
            unit_id=rewarded_ads.TEST_REWARDED_UNIT_ID,
            on_load=self.controller.loaded,
            on_open=self.controller.opened,
            on_close=self.controller.dismissed,
            on_error=self.controller.failed,
            on_reward=self.controller.earned,
        )
        self.controller.factory = Mock(return_value=service)
        bridge_page = SimpleNamespace(
            session=SimpleNamespace(
                index={service._i: service}, after_event=AsyncMock()
            )
        )

        async def native_load(token):
            await service._trigger_event("load", {"request_id": token})

        async def native_show(token):
            await service._trigger_event("open", {"request_id": token})

        with patch.object(
            ft.BaseControl, "page", new_callable=PropertyMock, return_value=bridge_page
        ):
            with (
                patch.object(service, "load", native_load),
                patch.object(service, "show", native_show),
                patch.object(service, "dispose_ad", AsyncMock()),
            ):
                self.assertTrue(
                    await asyncio.wait_for(self.controller.request("food"), timeout=0.5)
                )
                payload = {
                    "request_id": self.controller.token,
                    "amount": 1,
                    "type": "Бонус",
                }
                await service._trigger_event("reward", payload)
                await service._trigger_event("reward", payload)
                await service._trigger_event(
                    "close", {"request_id": self.controller.token}
                )
                self.assertEqual(
                    (self.session.state.food, self.session.state.reward_count), (15, 1)
                )
                await self.controller.close()

    async def test_actual_flet_error_dispatch_keeps_sdk_reason_without_waiting_for_timeout(
        self,
    ):
        context_token = _context_page.set(None)
        self.addCleanup(_context_page.reset, context_token)
        service = rewarded_ads.RewardedAd(
            unit_id=rewarded_ads.TEST_REWARDED_UNIT_ID, on_error=self.controller.failed
        )
        self.controller.factory = Mock(return_value=service)
        bridge_page = SimpleNamespace(
            session=SimpleNamespace(
                index={service._i: service}, after_event=AsyncMock()
            )
        )

        async def native_failure(token):
            await service._trigger_event(
                "error",
                {
                    "request_id": token,
                    "stage": "load",
                    "code": 3,
                    "domain": "com.google.android.gms.ads",
                    "message": "No fill",
                },
            )

        with patch.object(
            ft.BaseControl, "page", new_callable=PropertyMock, return_value=bridge_page
        ):
            with (
                patch.object(service, "load", native_failure),
                patch.object(service, "dispose_ad", AsyncMock()),
            ):
                self.assertFalse(
                    await asyncio.wait_for(self.controller.request("food"), timeout=0.5)
                )
                self.assertEqual(self.controller.state.phase, "error")
                self.assertIn("code: 3", self.controller.state.error)
                self.assertIn("No fill", self.controller.state.error)
                self.assertEqual(
                    (self.session.state.food, self.session.state.reward_count), (0, 0)
                )
                await self.controller.close()

    async def test_loading_deadline_covers_a_stuck_native_rpc_and_allows_retry(self):
        self.controller.load_timeout = 0.02
        late_token = ""

        async def stuck(token):
            nonlocal late_token
            late_token = token
            await asyncio.Event().wait()

        self.service.load.side_effect = stuck
        self.assertFalse(
            await asyncio.wait_for(self.controller.request("food"), timeout=0.5)
        )
        self.assertIn("LoadTimeout", self.controller.state.error)
        self.service.cancel.assert_awaited_once()
        await self.controller.loaded(self.event(late_token))
        await self.controller.earned(self.event(late_token))
        self.assertEqual(self.session.state.reward_count, 0)

        async def ready(token):
            await self.controller.loaded(self.event(token))

        self.service.load.side_effect = ready
        self.assertTrue(await self.controller.request("food"))

    async def test_normal_request_restores_the_owner_unit_after_diagnostic(self):
        self.controller.unit_id = rewarded_ads.REWARDED_UNIT_ID
        self.assertTrue(await self.controller.request(diagnostic=True))
        await self.controller.dismissed(self.event())
        banner = SimpleNamespace(
            start=AsyncMock(),
            manager=SimpleNamespace(can_request_ads=AsyncMock(return_value=True)),
        )
        with patch.object(rewarded_ads, "get_ad_controller", return_value=banner):
            self.assertTrue(await self.controller.request("food"))
        self.assertEqual(
            self.factory.call_args.kwargs["unit_id"], rewarded_ads.REWARDED_UNIT_ID
        )
        self.service.dispose_ad.assert_awaited_once()
        await self.controller.earned(self.event())
        self.assertEqual(self.session.state.food, 15)

    async def test_failure_to_show_is_returned_as_failure_and_cannot_award(self):
        async def failure(token):
            await self.controller.failed(
                SimpleNamespace(
                    data={
                        "request_id": token,
                        "stage": "show",
                        "code": 0,
                        "message": "Unable to show",
                    }
                )
            )

        self.service.show.side_effect = failure
        self.assertFalse(await self.controller.request("food"))
        self.assertEqual(self.controller.state.phase, "error")
        self.assertIn("stage: show", self.controller.state.error)
        self.assertEqual(self.session.state.reward_count, 0)

    async def test_diagnostic_video_uses_google_unit_without_bonus_or_daily_limit(self):
        self.controller.unit_id = rewarded_ads.REWARDED_UNIT_ID
        self.session.state.reward_count = 4
        self.session.state.reward_day = 1000 // 86400
        before = self.session.state.to_dict()
        self.assertTrue(await self.controller.request(diagnostic=True))
        self.assertEqual(
            self.factory.call_args.kwargs["unit_id"], rewarded_ads.TEST_REWARDED_UNIT_ID
        )
        await self.controller.earned(self.event())
        await self.controller.dismissed(self.event())
        self.assertEqual(self.session.state.to_dict(), before)
        self.assertIn("Тестовое видео прошло", self.controller.state.message)


if __name__ == "__main__":
    unittest.main()
