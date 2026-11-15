"""Render the game first; restore identity and cloud state in background tasks."""

import flet as ft

from advertising import BannerFooter
from arena_screen import arena_screen
from display_mode import set_arena_expanded
from game_session import GameSession, demo_requested, preview_session
from main_screen import main_screen
from profile_screen import profile_screen
from scene_focus import FocusedScene
from shop_screen import shop_screen
from ui_shared import BG, page_gradient, tint, use_game
from feature_screens import FeatureScreen


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
            session.route=''
            session.robot_detail=''
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
    return ft.Column(
        controls=[
            ft.Container(
                content=ft.SafeArea(
                    content=ft.Container(
                        content=FocusedScene(page=page, session=session)
                        if expanded
                        else FeatureScreen(page=page,session=session) if session.route
                        else screens[selected_index](),
                        padding=ft.Padding.all(5)
                        if expanded
                        else ft.Padding.only(left=14, right=14, top=12, bottom=12),
                    ),
                    avoid_intrusions_bottom=False,
                ),
                expand=True,
                gradient=page_gradient(state.accent),
            ),
            ft.NavigationBar(
                selected_index=selected_index,
                on_change=navigate,
                visible=not expanded,
                height=68,
                bgcolor=tint(state.accent, 0.95),
                indicator_color=tint(state.accent, 0.78),
                destinations=[
                    ft.NavigationBarDestination(
                        icon=ft.Icons.HOME_ROUNDED, label="Мастерская"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.SMART_TOY_ROUNDED, label="Роботы"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.SPORTS_MARTIAL_ARTS_ROUNDED, label="Арена"
                    ),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.PERSON_OUTLINE_ROUNDED, label="Профиль"
                    ),
                ],
            ),
            BannerFooter(page=page, key="advertising-footer") if not expanded and selected_index!=2 and session.route!='factory' else ft.Container(height=0),
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
    import os
    import sys
    from pathlib import Path

    from flet.utils import is_embedded

    if sys.platform == "win32" and not is_embedded() and not os.getenv("FLET_FORCE_WEB_SERVER") and not os.getenv("FLET_SERVER_PORT"):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import runpy

        runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/windows_game.py"), run_name="__main__")
    else:
        ft.run(main)
