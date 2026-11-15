"""A client clock; countdowns keep moving without a Python/UI round trip."""
import flet as ft


@ft.control("GameCountdown")
class GameCountdown(ft.Text):
    seconds: float = 0
    countdown_id: str = ""
    ready_text: str = "Можно забирать награду!"
    on_expire: ft.ControlEventHandler | None = None
