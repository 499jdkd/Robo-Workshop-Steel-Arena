"""Opt-in video rewards. Only the native earned callback grants a bonus."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, replace
from typing import Optional

import flet as ft
import flet_ads as ads

from advertising import get_ad_controller, supports_banner
from progression import video_available, video_offer
from ui_shared import INK, MUTED, button_style, card, use_game

TEST_REWARDED_UNIT_ID = "ca-app-pub-3940256099942544/5224354917"
# A standard rewarded unit is required here; a banner ID is never reused.
REWARDED_UNIT_ID = "ca-app-pub-4765036354233528/1280918260"
LOAD_TIMEOUT = 15
logger = logging.getLogger(__name__)


@ft.control("RewardedAd")
class RewardedAd(ft.Service):
    unit_id: str
    request: ads.AdRequest = field(
        default_factory=lambda: ads.AdRequest(
            non_personalized_ads=True, http_timeout=20000
        )
    )
    # Event[Any] preserves native dictionary payloads in event.data. An
    # unparameterized ControlEventHandler resolves to Event[TypeVar] in Flet
    # 1.0.4, which silently discards request_id, code and message.
    on_load: Optional[ft.EventHandler[ft.ControlEvent]] = None
    on_error: Optional[ft.EventHandler[ft.ControlEvent]] = None
    on_open: Optional[ft.EventHandler[ft.ControlEvent]] = None
    on_close: Optional[ft.EventHandler[ft.ControlEvent]] = None
    on_reward: Optional[ft.EventHandler[ft.ControlEvent]] = None

    async def load(self, token):
        await self._invoke_method("load", {"request_id": token})

    async def show(self, token):
        await self._invoke_method("show", {"request_id": token})

    async def cancel(self):
        await self._invoke_method("cancel")

    async def dispose_ad(self):
        await self._invoke_method("dispose")


@dataclass(frozen=True)
class RewardState:
    phase: str = "idle"
    message: str = ""
    offer_title: str = ""
    error: str = ""
    attempts: int = 0
    diagnostic: bool = False


def event_data(event):
    data = getattr(event, "data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            return {}
    return data if isinstance(data, dict) else {}


class RewardController:
    def __init__(
        self,
        page,
        session,
        *,
        unit_id=REWARDED_UNIT_ID,
        factory=RewardedAd,
        load_timeout=LOAD_TIMEOUT,
    ):
        self.page, self.session, self.unit_id = page, session, unit_id
        self.factory = factory
        self.state = RewardState()
        self.listeners = []
        self.service = None
        self.closed = False
        self.token = ""
        self.offer = None
        self._loaded = None
        self._request_task = None
        self._earned = False
        self.load_timeout = load_timeout
        self._service_unit = ""
        self._diagnostic = False

    @property
    def test_mode(self):
        return self.unit_id == TEST_REWARDED_UNIT_ID

    @property
    def alive(self):
        return not self.closed and self.session.ui_alive

    def subscribe(self, callback):
        self.listeners.append(callback)

        def remove():
            if callback in self.listeners:
                self.listeners.remove(callback)

        return remove

    def update(self, **changes):
        if not self.alive:
            return
        self.state = replace(self.state, **changes)
        for callback in tuple(self.listeners):
            callback()

    def matches(self, event):
        return (
            self.alive
            and self.token
            and event_data(event).get("request_id") == self.token
        )

    async def loaded(self, event):
        if self.matches(event) and self._loaded is not None and not self._loaded.done():
            self._loaded.set_result(True)

    async def failed(self, event):
        if not self.matches(event):
            return
        if self._loaded is not None and not self._loaded.done():
            self._loaded.set_result(False)
        data = event_data(event)
        code, message = (
            data.get("code"),
            str(data.get("message", "Ошибка рекламного SDK")),
        )
        friendly = (
            "Сейчас нет подходящего видео. Попробуй позже"
            if code == 3
            else "Не удалось связаться с рекламной сетью. Попробуй позже"
            if code == 2
            else "Видео сейчас недоступно. Лимит бонусов не изменился"
        )
        if "403" in message:
            friendly = "AdMob отклонил запрос видео. Открой подробности"
        details = "\n".join(
            f"{key}: {data[key]}"
            for key in ("stage", "code", "domain", "message", "response_info")
            if data.get(key) is not None
        )
        logger.warning("Rewarded ad failed: %s", details)
        self.update(phase="error", message=friendly, error=details)
        self.token = ""

    async def opened(self, event):
        if self.matches(event):
            self.update(phase="showing", message="")

    async def earned(self, event):
        if (
            not self.matches(event)
            or self._earned
            or not self.offer
            or self.state.phase != "showing"
        ):
            return
        self._earned = True
        if self._diagnostic:
            self.update(
                message="Тестовое видео прошло. Игровые бонусы и лимит не изменены"
            )
            return
        result = self.session.claim_video_reward(self.token, self.offer)
        self.update(message=result.message)

    async def dismissed(self, event):
        if self.matches(event):
            self.update(
                phase="idle",
                message=self.state.message
                if self._earned
                else "Видео закрыто без награды",
            )

    async def request(self, kind="food", target="", *, diagnostic=False):
        if not self.alive or self.state.phase in {"loading", "showing"}:
            return False
        if not supports_banner(self.page):
            self.update(message="Видеобонусы доступны в Android-приложении")
            return False
        offer = (
            {"title": "Тестовое видео Google · без награды и дохода"}
            if diagnostic
            else video_offer(self.session.state, kind, target, self.session.clock())
        )
        remaining, cooldown = video_available(self.session.state, self.session.clock())
        if not diagnostic and (not offer or not remaining or cooldown):
            self.update(
                message=f"Следующий бонус через {cooldown} с"
                if cooldown
                else "Сегодняшние видеобонусы получены"
            )
            return False
        self._request_task = asyncio.current_task()
        self.token = uuid.uuid4().hex
        token = self.token
        self.offer, self._earned = dict(offer), False
        self._diagnostic = diagnostic
        request_unit = TEST_REWARDED_UNIT_ID if diagnostic else self.unit_id
        self.update(
            phase="loading",
            message="Готовим видео…",
            offer_title=offer["title"],
            error="",
            diagnostic=diagnostic,
            attempts=self.state.attempts + 1,
        )
        stage = "consent"
        try:
            if request_unit != TEST_REWARDED_UNIT_ID:
                banner = get_ad_controller(self.page)
                await banner.start()
                if banner.manager is None or not await asyncio.wait_for(
                    banner.manager.can_request_ads(), timeout=5
                ):
                    self.update(
                        phase="error",
                        message="Разрешение на рекламу пока не получено",
                        error="UMP: canRequestAds=false",
                    )
                    return False
            if not self.alive or token != self.token:
                return False
            stage = "prepare"
            if self.service is not None and self._service_unit != request_unit:
                await asyncio.wait_for(self.service.dispose_ad(), timeout=3)
                self.service = None
            if self.service is None:
                self.service = self.factory(
                    unit_id=request_unit,
                    on_load=self.loaded,
                    on_error=self.failed,
                    on_open=self.opened,
                    on_close=self.dismissed,
                    on_reward=self.earned,
                )
                self._service_unit = request_unit
            self._loaded = asyncio.get_running_loop().create_future()

            async def wait_for_video():
                await self.service.load(token)
                return await self._loaded

            stage = "load"
            ready = await asyncio.wait_for(wait_for_video(), timeout=self.load_timeout)
            if not ready or not self.alive or token != self.token:
                return False
            self.update(phase="showing", message="Открываем видео…")
            stage = "show"
            await asyncio.wait_for(self.service.show(token), timeout=5)
            return bool(
                self.alive and token == self.token and self.state.phase != "error"
            )
        except asyncio.CancelledError:
            if self.alive and token == self.token:
                self.token = ""
                self.update(phase="idle", message="Загрузка видео отменена")
            return False
        except Exception as error:
            self.token = ""
            details = f"{type(error).__name__}: {error}"
            if isinstance(error, asyncio.TimeoutError):
                details = (
                    f"{stage.title()}Timeout: превышено время ожидания на этапе {stage}"
                )
                if stage == "load":
                    details += f" ({self.load_timeout:g} с)"
            logger.warning("Rewarded video bridge: %s", details)
            self.update(
                phase="error",
                message="Не удалось загрузить видео. Лимит бонусов не изменился",
                error=details,
            )
            if self.service is not None:
                try:
                    await asyncio.wait_for(self.service.cancel(), timeout=3)
                except Exception:
                    pass
            return False
        finally:
            if self._request_task is asyncio.current_task():
                self._request_task = None

    async def cancel_pending(self):
        if self.state.phase != "loading":
            return
        self.token = ""
        if (
            self._request_task is not None
            and self._request_task is not asyncio.current_task()
        ):
            self._request_task.cancel()
        if self._loaded is not None and not self._loaded.done():
            self._loaded.set_result(False)
        if self.service is not None:
            try:
                await asyncio.wait_for(self.service.cancel(), timeout=3)
            except Exception:
                pass
        self.update(phase="idle", message="")

    async def close(self):
        await self.cancel_pending()
        self.closed = True
        self.listeners.clear()
        if self.service is not None:
            try:
                await self.service.dispose_ad()
            except Exception:
                pass


def get_reward_controller(page, session):
    controller = getattr(page, "_clicker_rewarded", None)
    if controller is None or controller.closed or controller.session is not session:
        controller = RewardController(page, session)
        page._clicker_rewarded = controller
    return controller


@ft.component
def RewardPanel(page, session, compact=False):
    state = use_game(session)
    controller = get_reward_controller(page, session)
    _, render = ft.use_state(0)
    details_open, set_details_open = ft.use_state(False)
    active = ft.use_ref(False)
    unsubscribe = ft.use_ref(None)

    def connect():
        active.current = True
        unsubscribe.current = controller.subscribe(
            lambda: render(lambda value: value + 1) if active.current else None
        )

    def disconnect():
        active.current = False
        if unsubscribe.current:
            unsubscribe.current()

    ft.use_effect(connect, [controller], cleanup=disconnect)
    remaining, cooldown = video_available(state, session.clock())
    busy = controller.state.phase in {"loading", "showing"}
    controls = [
        ft.Row(
            [
                ft.Icon(ft.Icons.ONDEMAND_VIDEO_ROUNDED, color=state.accent, size=22),
                ft.Text(
                    "Бонусы за видео",
                    size=14,
                    color=INK,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                ),
                ft.Text(f"{remaining}/4 сегодня", size=10, color=MUTED),
            ],
            spacing=8,
        )
    ]
    if controller.test_mode:
        controls.append(
            ft.Text("Тестовое видео Google · дохода нет", size=10, color=MUTED)
        )
    if not supports_banner(page):
        controls.append(
            ft.Text(
                "Видеобонусы доступны в Android. Всё развитие доступно и без рекламы",
                size=11,
                color=MUTED,
            )
        )
    else:

        async def cancel(_):
            await controller.cancel_pending()

        async def toggle_details(_):
            set_details_open(lambda value: not value)

        async def test_video(_):
            await controller.request(diagnostic=True)

        if controller.state.message:
            controls.append(
                ft.Row(
                    [
                        *(
                            [ft.ProgressRing(width=20, height=20, stroke_width=2)]
                            if busy
                            else []
                        ),
                        ft.Text(
                            controller.state.message,
                            size=12,
                            color=INK,
                            expand=True,
                            key="reward-status",
                        ),
                    ],
                    spacing=8,
                )
            )
        if busy:
            controls.append(ft.Text(controller.state.offer_title, size=11, color=MUTED))
            if controller.state.phase == "loading":
                controls.append(
                    ft.TextButton(
                        "Отменить загрузку", on_click=cancel, key="reward-cancel"
                    )
                )

        kinds = (
            ("food",)
            if compact
            else (
                "food",
                "boost",
                "training",
                "incubator",
                "gold",
                "container",
                "order_speed",
                "season_xp",
            )
        )
        for kind in () if busy else kinds:
            offer = video_offer(state, kind, state.active_robot, session.clock())
            if not offer:
                continue

            async def watch(_, choice=kind):
                await controller.request(choice, session.state.active_robot)

            controls.append(
                ft.Button(
                    "Видео · " + offer["title"],
                    icon=ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED,
                    key=f"reward-{kind}",
                    on_click=watch,
                    disabled=busy or not remaining or bool(cooldown),
                    style=button_style(state.accent, secondary=True),
                    width=float("inf"),
                )
            )
        if cooldown:
            controls.append(
                ft.Text(f"Следующее видео через {cooldown} с", size=10, color=MUTED)
            )
        if controller.state.error and not busy:
            controls.append(
                ft.TextButton(
                    "Скрыть подробности"
                    if details_open
                    else "Подробности ошибки видео",
                    on_click=toggle_details,
                    key="reward-details",
                )
            )
            if details_open:
                controls.extend(
                    [
                        ft.Container(
                            ft.Column(
                                [
                                    ft.Text(
                                        f"Блок: {TEST_REWARDED_UNIT_ID if controller.state.diagnostic else controller.unit_id}\nПопытка: {controller.state.attempts}\n{controller.state.error}",
                                        size=10,
                                        color=MUTED,
                                        selectable=True,
                                    )
                                ],
                                scroll=ft.ScrollMode.AUTO,
                            ),
                            height=135,
                        ),
                        ft.Text(
                            "Тест Google проверяет загрузку, без награды и дохода",
                            size=10,
                            color=MUTED,
                        ),
                        ft.TextButton(
                            "Проверить тестовое видео",
                            on_click=test_video,
                            key="reward-test",
                        ),
                    ]
                )
    return card(ft.Column(controls, spacing=9), padding=13)
