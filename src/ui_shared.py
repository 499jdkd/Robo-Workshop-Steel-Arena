"""Small Flet controls and a single subscription hook for each screen."""

import flet as ft

from gameplay import compact

BG = "#09152B"
INK = "#F1F7FF"
MUTED = "#A3B7D5"
GOLD = "#FFD05A"
GREEN = "#61E7A4"
PANEL = "#183254"
EDGE = "#416B9D"


def tint(color, white=0.9):
    color = color.lstrip("#")[-6:]
    base=(12,28,51)
    weight=.14+(1-white)*.65
    return "#" + "".join(f"{round(int(color[i:i+2],16)*weight+base[j]*(1-weight)):02X}" for j,i in enumerate((0,2,4)))


def page_gradient(accent):
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=["#122B50", tint(accent, 0.86), "#071225"],
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
    if bgcolor in {"white", "#FFFFFF"}:
        bgcolor=PANEL
    elif bgcolor.startswith('#') and len(bgcolor)==7:
        rgb=[int(bgcolor[i:i+2],16) for i in (1,3,5)]
        if sum(rgb)>510:bgcolor=tint(bgcolor,.84)
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border_radius=16,
        border=kwargs.pop('border',ft.Border.all(1,EDGE)),
        gradient=kwargs.pop('gradient',ft.LinearGradient(begin=ft.Alignment.TOP_LEFT,end=ft.Alignment.BOTTOM_RIGHT,colors=[bgcolor,"#10233E"])),
        padding=padding,
        shadow=kwargs.pop(
            "shadow",
            ft.BoxShadow(blur_radius=8, color="#77020B1B", offset=ft.Offset(0, 4)),
        ),
        **kwargs,
    )


def button_style(accent, *, secondary=False):
    rgb=[int(accent.lstrip('#')[-6:][i:i+2],16) for i in (0,2,4)]
    foreground='#102443' if sum(channel*weight for channel,weight in zip(rgb,(.2126,.7152,.0722)))>160 else '#FFFFFF'
    return ft.ButtonStyle(
        bgcolor=tint(accent, 0.91) if secondary else accent,
        color=INK if secondary else foreground,
        elevation=3 if not secondary else 1,
        shadow_color="#050E21",
        side=ft.BorderSide(1, "#588DBD" if secondary else "#A4D8FF"),
        shape=ft.RoundedRectangleBorder(
            radius=10
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        text_style=ft.TextStyle(size=12,weight=ft.FontWeight.BOLD,font_family='Roboto'),
    )


def heading(title, subtitle="", trailing=None):
    return ft.Row(
        controls=[
            ft.Column(
                [
                    ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=INK),
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
        bgcolor="#31425A",
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
