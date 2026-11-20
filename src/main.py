"""Render the game first; restore identity and cloud state in background tasks."""

# Editors may run this file with system Python instead of the project environment.
# Switch before importing optional Flet extensions; packaged apps keep their runtime.
if __name__ == "__main__":
    import importlib.util
    import os
    from pathlib import Path
    import sys

    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        project_python = Path(__file__).resolve().parents[1] / ".venv/Scripts/python.exe"
        if (
            project_python.is_file()
            and Path(sys.executable).resolve() != project_python.resolve()
            and importlib.util.find_spec("flet_ads") is None
        ):
            os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])

import flet as ft
from importlib import import_module

from advertising import BannerFooter
from display_mode import set_arena_expanded
from game_session import GameSession, demo_requested, preview_session
from main_screen import main_screen
from ui_shared import BG, page_gradient, tint, use_game


def lazy_screen(module, name):
    def render(*args, **kwargs):
        return getattr(import_module(module), name)(*args, **kwargs)
    return render


arena_screen = lazy_screen("arena_screen", "arena_screen")
profile_screen = lazy_screen("profile_screen", "profile_screen")
shop_screen = lazy_screen("shop_screen", "shop_screen")
FocusedScene = lazy_screen("scene_focus", "FocusedScene")
FeatureScreen = lazy_screen("feature_screens", "FeatureScreen")
RobotDetail = lazy_screen("collection_ui", "RobotDetail")


@ft.component
def App(page: ft.Page, device_id: str = "", session=None, start_tab=0):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    selected_index, set_selected_index = ft.use_state(start_tab)
    expanded = bool(session.focus_scene)

    async def navigate(event):
        index = event.control.selected_index
        reward = getattr(page, "_clicker_rewarded", None)
        if reward is not None:
            await reward.cancel_pending()
        if session.arena_expanded and index != 2:
            await set_arena_expanded(page, session, False)
        if session.ui_alive:
            session.route = ""
            session.robot_detail = ""
            session.robot_detail_return = ""
            set_selected_index(index)

    screens = (
        lambda: main_screen(
            page,
            session.device_id,
            session=session,
            on_collection=lambda _: set_selected_index(1),
            on_arena=lambda _: set_selected_index(2),
        ),
        lambda: shop_screen(
            page,
            session.device_id,
            session=session,
            on_home=lambda _: set_selected_index(0),
        ),
        lambda: arena_screen(
            page,
            session.device_id,
            session=session,
            on_home=lambda _: set_selected_index(0),
        ),
        lambda: profile_screen(page, session.device_id, session=session),
    )
    body = (
        FocusedScene(page=page, session=session)
        if expanded
        else FeatureScreen(page=page, session=session)
        if session.route
        else RobotDetail(page=page, session=session, identity=session.robot_detail)
        if session.robot_detail
        else screens[selected_index]()
    )
    destination = (
        f"{selected_index}:{session.route}:{session.robot_detail}:{session.focus_scene}"
    )
    return ft.Column(
        controls=[
            ft.Container(
                key=destination,
                content=ft.SafeArea(
                    content=ft.Container(
                        content=body,
                        padding=ft.Padding.all(5)
                        if expanded
                        else ft.Padding.only(left=14, right=14, top=12, bottom=12),
                    ),
                    avoid_intrusions_bottom=expanded,
                ),
                expand=True,
                gradient=page_gradient(state.accent),
            ),
            ft.NavigationBar(
                key="main-navigation",
                selected_index=selected_index,
                on_change=navigate,
                visible=not expanded,
                height=80,
                label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
                label_padding=ft.Padding.only(top=3),
                bgcolor=tint(state.accent, 0.95),
                indicator_color=tint(state.accent, 0.08),
                border=ft.Border.only(top=ft.BorderSide(1, "#6488B3")),
                destinations=[
                    ft.NavigationBarDestination(
                        icon=ft.Icon(ft.Icons.HOME_ROUNDED, size=28), label="Мастерская"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icon(ft.Icons.SMART_TOY_ROUNDED, size=28), label="Роботы"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icon(ft.Icons.SPORTS_MARTIAL_ARTS_ROUNDED, size=28), label="Арена"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, size=28), label="Профиль"
                    ),
                ],
            ),
            ft.SafeArea(
                content=ft.Container(
                    BannerFooter(page=page, key="advertising-footer"),
                    padding=ft.Padding.only(top=12),
                    bgcolor=BG,
                ) if selected_index != 2 and session.route != "factory" else ft.Container(height=0),
                avoid_intrusions_top=False,
                maintain_bottom_view_padding=True,
            ) if not expanded else ft.Container(height=0),
        ],
        spacing=0,
        expand=True,
    )


async def main(page: ft.Page):
    demo = demo_requested()
    page.title = "Clicker · Робо-мастерская" + (" · Preview" if demo else "")
    page.window.width = 420
    page.window.height = 840
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    session = GameSession(page, demo=demo)
    page.theme = ft.Theme(color_scheme_seed=session.state.accent)
    prefs = None if demo else ft.SharedPreferences()

    # No network or platform storage RPC is awaited before the first render.
    page.render(App, page=page, device_id=session.device_id, session=session)
    session.start(prefs)

    async def disconnected(_):
        rewarded = getattr(page, "_clicker_rewarded", None)
        if rewarded is not None:
            await rewarded.close()
        advertising = getattr(page, "_clicker_advertising", None)
        if advertising is not None:
            await advertising.close()
        await session.close()

    async def connected(_):
        if session.closed:
            await session.close()
            page.render(App, page=page, device_id=session.device_id, session=session)
        session.start(prefs)

    async def lifecycle(event):
        state = getattr(event, "state", "")
        state = getattr(state, "value", str(state)).lower()
        if state == "resumed":
            session.resume()
        elif state in {"paused", "hidden", "detached"}:
            session.pause()

    page.on_disconnect = disconnected
    page.on_connect = connected
    page.on_app_lifecycle_state_change = lifecycle
    page.on_resize = lambda _: session.notify() if session.ui_alive else None
    return session


if __name__ == "__main__":
    from desktop_startup import run

    run(main)
