"""Interactive showroom for every robot, independent of ownership and game actions."""

import flet as ft

from game_animation import animated_scene
from game_ui import game_button
from robot_abilities import ABILITIES
from robot_catalog import ROBOT_BY_ID
from ui_shared import GOLD, INK, MUTED, card


def preview_stage(session, identity, *, height=300, expanded=False, on_expand=None):
    robot = ROBOT_BY_ID[identity]
    return card(ft.Stack([
        ft.Image("art/workshop-future-v1.png", width=float("inf"), height=height,
                 fit=ft.BoxFit.COVER, opacity=0.55, cache_width=900),
        ft.Container(animated_scene(session, identity=identity, expanded=expanded),
                     left=0, right=0, top=0, bottom=0),
        ft.Container(ft.Text(f"{robot.name} · интерактивный осмотр", color=INK, size=13,
                             weight=ft.FontWeight.BOLD), left=10, top=10, right=58,
                     padding=8, bgcolor="#CC122B49", border_radius=10),
        *([ft.Container(ft.IconButton(
            ft.Icons.CLOSE_FULLSCREEN_ROUNDED if expanded else ft.Icons.OPEN_IN_FULL_ROUNDED,
            on_click=on_expand, icon_color="white", width=48, height=48,
            key="robot-inspect-close" if expanded else "robot-inspect",
            tooltip="Закрыть осмотр" if expanded else "Осмотреть на весь экран"),
            right=6, top=5, bgcolor="#BB152D4B", border_radius=10)] if on_expand else []),
    ], height=height), padding=0, border=ft.Border.all(2, robot.color),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS)


def preview_controls(session, identity):
    ability = ABILITIES[identity]
    actions = [
        ("attack", "Импульс" if identity == "volt" else "Атака", "blue", ft.Icons.FLASH_ON_ROUNDED),
        ("special", "Навык", "purple", ft.Icons.AUTO_FIX_HIGH_ROUNDED),
        ("ultimate", "Супер", "gold", ft.Icons.AUTO_AWESOME_ROUNDED),
        ("guard", "Защита", "green", ft.Icons.SHIELD_ROUNDED),
    ]
    if identity in {"volt", "titan"}:
        actions += [
            ("quick", "Быстрый", "blue", ft.Icons.BOLT_ROUNDED),
            ("dodge", "Уворот", "blue", ft.Icons.DOUBLE_ARROW_ROUNDED),
            ("charge", "Фокус", "green", ft.Icons.BATTERY_CHARGING_FULL_ROUNDED),
            ("dance", "Танец", "purple", ft.Icons.MUSIC_NOTE_ROUNDED),
            ("victory", "Победа", "gold", ft.Icons.EMOJI_EVENTS_ROUNDED),
            ("defeat", "Отключение", "purple", ft.Icons.POWER_SETTINGS_NEW_ROUNDED),
        ]

    def show(action):
        async def play(_):
            session.preview_robot(identity, action)
        return play

    return card(ft.Column([
        ft.Text(ability.title, color=GOLD, size=17, weight=ft.FontWeight.BOLD),
        ft.Text(ability.choreography + ".", color=INK, size=12),
        ft.Text(ability.effect + ".", color=MUTED, size=12),
        ft.ResponsiveRow([
            ft.Container(game_button(label, show(action), kind=kind, icon=icon,
                                     key=f"preview-{action}-{identity}"), col=6)
            for action, label, kind, icon in actions
        ], spacing=8, run_spacing=8),
        ft.Text("Коснись робота — реакция. Коснись пола — движение. Удерживай — особый приём. Двигай пальцем — робот следит за ним. Масштаб: щипок или кнопки лупы.", color=MUTED, size=12),
        ft.Text("Демонстрация · без наград и расхода ресурсов. Экипировка остаётся прежней.",
                color="#80E3BC", size=11),
    ], spacing=10), padding=12)
