"""AdMob banner with consent, recoverable loading and a Windows layout preview."""

import asyncio
import logging
import time
from dataclasses import dataclass, replace

import flet as ft
import flet_ads as ads

logger = logging.getLogger(__name__)
# Fixed 320x50, matching AdSize.banner. Google documents this demo setup at:
# https://codelabs.developers.google.com/codelabs/admob-ads-in-flutter
TEST_BANNER_UNIT_ID = "ca-app-pub-3940256099942544/6300978111"
# Robot warrior's standard Banner_2 unit. Publisher units always use UMP.
BANNER_UNIT_ID = "ca-app-pub-4765036354233528/1108034582"
LOAD_TIMEOUT = 25
RETRY_DELAYS = (30, 60)


def is_demo_unit(unit_id):
    # Exact allowlist. An owner's ID can never enter the demo-only path.
    return unit_id == TEST_BANNER_UNIT_ID


@dataclass(frozen=True)
class AdConsentState:
    can_request_ads: bool = False
    privacy_options_required: bool = False
    error: str = ""


@dataclass(frozen=True)
class AdState:
    phase: str = "starting"
    allowed: bool = False
    privacy_required: bool = False
    generation: int = 0
    attempts: int = 0
    error: str = ""


def supports_banner(page):
    return (
        not getattr(page, "web", False)
        and getattr(page, "platform", None) == ft.PagePlatform.ANDROID
    )


async def refresh_consent(manager):
    error_text = ""
    try:
        await asyncio.wait_for(
            manager.request_consent_info_update(
                ads.ConsentRequestParameters(tag_for_under_age_of_consent=True)
            ),
            timeout=15,
        )
        # Do not time out an interactive form while the user is choosing.
        await manager.load_and_show_consent_form_if_required()
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"
        logger.warning("Could not refresh ad consent: %s", error_text)
    try:
        allowed = await asyncio.wait_for(manager.can_request_ads(), timeout=5)
        required = await asyncio.wait_for(
            manager.get_privacy_options_requirement_status(), timeout=5
        )
        return AdConsentState(
            allowed,
            required == ads.PrivacyOptionsRequirementStatus.REQUIRED,
            error_text,
        )
    except Exception as error:
        return AdConsentState(error=f"{type(error).__name__}: {error}")


class AdController:
    def __init__(
        self,
        page,
        *,
        unit_id=BANNER_UNIT_ID,
        manager_factory=ads.ConsentManager,
        clock=time.monotonic,
        sleep=asyncio.sleep,
    ):
        self.page, self.unit_id = page, unit_id
        self.demo = is_demo_unit(unit_id)
        self.manager_factory, self.clock, self.sleep = manager_factory, clock, sleep
        self.state = AdState(
            phase="starting" if supports_banner(page) else "unsupported"
        )
        self.manager = None
        self.listeners = []
        self._tasks = set()
        self._watchdog = self._retry = None
        self._cooldown = None
        self._started = self._closed = False
        self._failures = 0
        self._last_request = -1000000.0

    @property
    def alive(self):
        if self._closed:
            return False
        try:
            getattr(self.page, "session", None)
            return True
        except RuntimeError as error:
            if "destroyed session" not in str(error).lower():
                raise
            return False

    def subscribe(self, callback):
        if self._closed:
            return lambda: None
        self.listeners.append(callback)

        def unsubscribe():
            if callback in self.listeners:
                self.listeners.remove(callback)

        return unsubscribe

    def _update(self, **changes):
        if not self.alive:
            return
        self.state = replace(self.state, **changes)
        for listener in tuple(self.listeners):
            try:
                listener()
            except RuntimeError as error:
                if "destroyed session" not in str(error).lower():
                    raise
                self.listeners.clear()
                return

    def _spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _cancel(self, task):
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()

    async def start(self):
        if self._started or self._closed or not supports_banner(self.page):
            return
        self._started = True
        await self._prepare()

    async def _prepare(self):
        if not self.alive:
            return
        self._last_request = self.clock()
        self._cancel(self._cooldown)
        if not self.demo:
            self._update(phase="consent", allowed=False)
            if self.manager is None:
                try:
                    self.manager = self.manager_factory()
                except Exception as error:
                    self._update(
                        phase="blocked",
                        allowed=False,
                        error=f"{type(error).__name__}: {error}",
                    )
                    self._cooldown = self._spawn(self._retry_ready())
                    return
            consent = await refresh_consent(self.manager)
            if not self.alive:
                return
            self._update(privacy_required=consent.privacy_options_required)
            if not consent.can_request_ads:
                self._update(
                    phase="blocked",
                    allowed=False,
                    error=consent.error or "UMP: canRequestAds=false",
                )
                self._cooldown = self._spawn(self._retry_ready())
                return
        self._request()

    def _request(self):
        self._cancel(self._watchdog)
        self._last_request = self.clock()
        self._update(
            phase="loading",
            allowed=True,
            generation=self.state.generation + 1,
            attempts=self.state.attempts + 1,
            error="",
        )
        self._watchdog = self._spawn(self._load_deadline(self.state.generation))

    async def _load_deadline(self, generation):
        await self.sleep(LOAD_TIMEOUT)
        if (
            self.alive
            and self.state.phase == "loading"
            and generation == self.state.generation
        ):
            self.failed(
                generation,
                "Баннер не ответил за 25 секунд. Проверь подключение к интернету",
            )

    def loaded(self, generation):
        if (
            self.alive
            and generation == self.state.generation
            and self.state.phase in {"loading", "loaded"}
        ):
            self._failures = 0
            self._cancel(self._watchdog)
            self._update(phase="loaded", error="")

    def failed(self, generation, detail):
        if (
            not self.alive
            or generation != self.state.generation
            or self.state.phase not in {"loading", "loaded"}
        ):
            return
        self._cancel(self._watchdog)
        self._last_request = self.clock()
        self._failures += 1
        logger.warning("Banner load failed: %s", detail)
        self._update(phase="failed", allowed=False, error=str(detail)[:1000])
        self._cooldown = self._spawn(self._retry_ready())
        if self._failures <= len(RETRY_DELAYS):
            self._cancel(self._retry)
            self._retry = self._spawn(
                self._retry_later(RETRY_DELAYS[self._failures - 1])
            )

    async def _retry_later(self, delay):
        await self.sleep(delay)
        if self.alive and self.state.phase == "failed":
            await self._prepare()

    async def _retry_ready(self):
        await self.sleep(30)
        if self.alive and self.state.phase in {"failed", "blocked"}:
            self._update()

    @property
    def can_retry(self):
        return (
            self.alive
            and self.state.phase in {"failed", "blocked"}
            and self.clock() - self._last_request >= 30
        )

    async def retry(self):
        if not self.can_retry:
            return False
        self._cancel(self._retry)
        self._failures = 0
        await self._prepare()
        return True

    async def privacy_options(self):
        if not self.alive or self.manager is None:
            return
        try:
            await self.manager.show_privacy_options_form()
            self._cancel(self._watchdog)
            self._cancel(self._retry)
            await self._prepare()
        except Exception as error:
            self._update(error=f"{type(error).__name__}: {error}")

    def dispose(self):
        self._closed = True
        self.listeners.clear()
        for task in tuple(self._tasks):
            self._cancel(task)

    async def close(self):
        self.dispose()
        tasks = [task for task in self._tasks if task is not asyncio.current_task()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


def get_ad_controller(page):
    controller = getattr(page, "_clicker_advertising", None)
    if controller is None or controller._closed:
        controller = AdController(page, unit_id=BANNER_UNIT_ID)
        page._clicker_advertising = controller
    return controller


def use_ad_state(controller):
    _, refresh = ft.use_state(0)
    subscription, active = ft.use_ref(None), ft.use_ref(False)

    def connect():
        active.current = True
        subscription.current = controller.subscribe(
            lambda: refresh(lambda value: value + 1) if active.current else None
        )

    def disconnect():
        active.current = False
        if subscription.current is not None:
            subscription.current()
            subscription.current = None

    ft.use_effect(connect, [controller], cleanup=disconnect)
    return controller.state


def banner_view(controller):
    state = controller.state

    async def retry(_):
        await controller.retry()

    async def privacy(_):
        await controller.privacy_options()

    async def loaded(_):
        controller.loaded(state.generation)

    async def failed(event):
        controller.failed(state.generation, event.data)

    controls = []
    if controller.demo:
        controls.append(ft.Text("Тестовая реклама", size=10, color=ft.Colors.GREY_600))
    if state.allowed:
        controls.append(
            ads.BannerAd(
                key=f"admob-banner-{state.generation}",
                unit_id=controller.unit_id,
                request=ads.AdRequest(non_personalized_ads=True, http_timeout=20000),
                width=320,
                height=50,
                on_load=loaded,
                on_error=failed,
            )
        )
    else:
        text = (
            "Подключаем рекламу…"
            if state.phase in {"starting", "consent"}
            else "Реклама сейчас недоступна"
        )
        controls.append(
            ft.Row(
                [
                    ft.Text(text, size=11, color=ft.Colors.GREY_600, expand=True),
                    ft.TextButton(
                        "Повторить", on_click=retry, disabled=not controller.can_retry
                    ),
                ],
                width=320,
                spacing=6,
            )
        )
    if state.privacy_required:
        controls.append(ft.TextButton("Настройки рекламы", on_click=privacy))
    return ft.Container(
        padding=ft.Padding.only(top=8),
        alignment=ft.Alignment.CENTER,
        content=ft.SafeArea(
            avoid_intrusions_top=False,
            content=ft.Column(
                controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                tight=True,
            ),
        ),
    )


def windows_preview():
    return ft.Container(
        padding=ft.Padding.only(top=12, bottom=8),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Text(
                    "Предпросмотр места рекламы", size=10, color=ft.Colors.GREY_600
                ),
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.AD_UNITS_ROUNDED, color="#7773B7", size=26
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Баннер в Android-приложении",
                                        size=12,
                                        color="#4D4B70",
                                    ),
                                    ft.Text(
                                        "Макет на ПК · без рекламных показов",
                                        size=10,
                                        color="#77738C",
                                    ),
                                ],
                                spacing=3,
                            ),
                        ],
                        spacing=10,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    width=320,
                    height=50,
                    bgcolor="#EEEDF6",
                    border_radius=10,
                ),
            ],
            spacing=4,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


@ft.component
def BannerFooter(page):
    if not supports_banner(page):
        if (
            not getattr(page, "web", False)
            and getattr(page, "platform", None) == ft.PagePlatform.WINDOWS
        ):
            return windows_preview()
        return ft.Container(height=0)
    controller = get_ad_controller(page)
    use_ad_state(controller)
    lifecycle = ft.use_ref(None)

    def boot():
        lifecycle.current = controller
        controller._spawn(controller.start())

    def cleanup():
        previous = lifecycle.current
        lifecycle.current = None
        if previous is not None:
            previous.dispose()

    ft.use_effect(boot, [controller], cleanup=cleanup)
    return banner_view(controller)


@ft.component
def AdDiagnostics(page):
    controller = get_ad_controller(page)
    state = use_ad_state(controller)
    expanded, set_expanded = ft.use_state(False)
    supported = supports_banner(page)
    descriptions = {
        "starting": "Ожидает загрузки",
        "consent": "Проверяем настройки согласия",
        "loading": "Загружается",
        "loaded": "Баннер загружен",
        "failed": "Не удалось загрузить",
        "blocked": "Нужны настройки согласия AdMob",
        "unsupported": "Настоящие объявления доступны в Android APK",
    }

    async def retry(_):
        await controller.retry()

    async def toggle(_):
        set_expanded(not expanded)

    controls = [
        ft.Text("Реклама", size=15, weight=ft.FontWeight.BOLD, color="#24344B"),
        ft.Text(descriptions[state.phase], size=12, color="#7B8799"),
    ]
    if controller.demo:
        controls.append(
            ft.Text(
                "Сейчас используются объявления Google для проверки. Они не приносят доход",
                size=11,
                color="#7B8799",
            )
        )
    if supported:
        controls.append(
            ft.TextButton(
                "Скрыть подробности" if expanded else "Проверить рекламу",
                on_click=toggle,
            )
        )
    if supported and expanded:
        controls.append(
            ft.Text(
                f"Рекламный блок: {controller.unit_id}",
                size=10,
                color="#7B8799",
                selectable=True,
            )
        )
        controls.append(
            ft.Text(f"Попыток загрузки: {state.attempts}", size=10, color="#7B8799")
        )
        if state.error:
            controls.append(
                ft.Text(state.error, size=10, color="#925E59", selectable=True)
            )
        controls.append(
            ft.Button(
                "Повторить загрузку", on_click=retry, disabled=not controller.can_retry
            )
        )
    elif not supported:
        controls.append(
            ft.Text(
                "Нижний блок на компьютере показывает расположение баннера. Проверяй AdMob в установленной APK на телефоне",
                size=11,
                color="#7B8799",
            )
        )
    return ft.Container(
        ft.Column(controls, spacing=9), padding=16, bgcolor="white", border_radius=20
    )
