"""Expand a single scene; restore the ordinary app after closing it."""

import flet as ft
import os
import httpx


async def set_scene_focus(page, session, scene=""):
    if not session.ui_alive:
        return
    if scene not in {"", "battle", "workshop", "online-battle"}:
        return
    enabled = bool(scene)
    pending = getattr(page, "_clicker_rewarded", None)
    if pending is not None:
        await pending.cancel_pending()
    previous = session.focus_scene
    session.focus_scene = scene
    session.arena_expanded = scene in {"battle", "online-battle"}
    session.notify()
    try:
        if getattr(page, "web", False) and os.getenv("CLICKER_DESKTOP_HOST_URL"):
            async with httpx.AsyncClient(timeout=2) as client:
                await client.post(
                    os.environ["CLICKER_DESKTOP_HOST_URL"] + "/host/scene",
                    json={"expanded": enabled},
                    headers={"X-Clicker-Host": os.getenv("CLICKER_HOST_TOKEN", "")},
                )
        elif not getattr(page, "web", False) and getattr(page, "platform", None) in {
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.IOS,
        }:
            orientations = (
                [
                    ft.DeviceOrientation.LANDSCAPE_LEFT,
                    ft.DeviceOrientation.LANDSCAPE_RIGHT,
                ]
                if enabled
                else [ft.DeviceOrientation.PORTRAIT_UP]
            )
            await page.set_allowed_device_orientations(orientations)
        elif (
            not getattr(page, "web", False)
            and getattr(page, "window", None) is not None
        ):
            if enabled and not previous:
                session._focus_window_size = (
                    getattr(page.window, "width", None) or 420,
                    getattr(page.window, "height", None) or 840,
                )
                page.window.width, page.window.height = 960, 540
            elif not enabled and session._focus_window_size:
                page.window.width, page.window.height = session._focus_window_size
                session._focus_window_size = None
            if callable(getattr(page, "update", None)):
                page.update()
    except Exception as error:
        # The battle remains playable on tablets where the OS ignores rotation.
        session.tell(
            f"Сцена открыта; поворот экрана недоступен ({type(error).__name__})"
            if enabled
            else "Обычный вид восстановлен"
        )
    if session.ui_alive:
        session.notify()


async def set_arena_expanded(page, session, enabled):
    await set_scene_focus(page, session, "battle" if enabled else "")
