"""Small Flet controls and a single subscription hook for each screen."""

import flet as ft

from gameplay import compact

BG = "#F5F7FB"
INK = "#24344B"
MUTED = "#7B8799"
GOLD = "#E6A72D"
GREEN = "#258E79"


def tint(color, white=0.9):
    color = color.lstrip("#")[-6:]
    return "#" + "".join(
        f"{round(int(color[i : i + 2], 16) * (1 - white) + 255 * white):02X}"
        for i in (0, 2, 4)
    )


def page_gradient(accent):
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[tint(accent, 0.83), tint(accent, 0.96), "#F8F5FD"],
    )


def badge(name, size=34):
    return ft.Image(f"art/icons/{name}.svg", width=size, height=size)


def use_game(session):
    _, refresh = ft.use_state(0)
    subscription = ft.use_ref(None)
    active = ft.use_ref(False)

    def connect():
        active.current = True

        def changed():
            if active.current:
                refresh(lambda value: value + 1)

        subscription.current = session.subscribe(changed)

    def disconnect():
        active.current = False
        if subscription.current is not None:
            subscription.current()
            subscription.current = None

    ft.use_effect(connect, [session], cleanup=disconnect)
    return session.state


def card(content, *, padding=16, bgcolor="white", **kwargs):
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border_radius=20,
        padding=padding,
        shadow=kwargs.pop(
            "shadow",
            ft.BoxShadow(blur_radius=12, color="#0924344B", offset=ft.Offset(0, 3)),
        ),
        **kwargs,
    )


def button_style(accent, *, secondary=False):
    return ft.ButtonStyle(
        bgcolor=tint(accent, 0.91) if secondary else accent,
        color=accent if secondary else "white",
        elevation=0,
        side=ft.BorderSide(0, "#00000000", style=ft.BorderStyle.NONE),
        shape=ft.RoundedRectangleBorder(
            radius=12, side=ft.BorderSide(0, "#00000000", style=ft.BorderStyle.NONE)
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
    )


def heading(title, subtitle="", trailing=None):
    return ft.Row(
        controls=[
            ft.Column(
                [
                    ft.Text(title, size=25, weight=ft.FontWeight.BOLD, color=INK),
                    *([ft.Text(subtitle, size=12, color=MUTED)] if subtitle else []),
                ],
                spacing=3,
                expand=True,
            ),
            *([trailing] if trailing else []),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def wallet(state):
    return card(
        ft.Row(
            [
                badge("credits", 30),
                ft.Text(
                    compact(state.coin), size=19, weight=ft.FontWeight.BOLD, color=INK
                ),
            ],
            spacing=7,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
        bgcolor="#FFF5D8",
    )


def notice(session):
    if not session.notice:
        return ft.Container(height=0)
    return card(
        ft.Row(
            [
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=19, color=GOLD),
                ft.Text(session.notice, size=12, color=INK, expand=True),
            ],
            spacing=9,
        ),
        padding=12,
        bgcolor="#FFF6DC",
    )


def saving_status(session):
    text = {
        "loading": "Открываем сохранение…",
        "online": "Прогресс сохранён",
        "offline": "Сохранено на устройстве",
        "local": "Твоя мастерская",
    }.get(session.connection, "Сохранено на устройстве")
    icon = (
        ft.Icons.CLOUD_DONE_ROUNDED
        if session.connection == "online"
        else ft.Icons.CLOUD_OFF_ROUNDED
    )
    return ft.Row(
        [
            ft.Icon(icon, size=13, color=MUTED),
            ft.Text(text, size=10, color=MUTED),
        ],
        spacing=5,
    )
