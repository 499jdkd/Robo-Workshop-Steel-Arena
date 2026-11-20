import flet as ft

from advertising import AdDiagnostics
from game_session import preview_session
from gameplay import GOALS, PALETTES, STAGES, compact
from progression import selected_avatar
from progression_ui import avatar_picker, project_gallery
from robot_catalog import ROBOTS
from robot_motion import robot_actor
from ui_shared import (
    GOLD,
    INK,
    MUTED,
    badge,
    button_style,
    card,
    heading,
    notice,
    page_gradient,
    saving_status,
    tint,
    use_game,
    wallet,
)


@ft.component
def ProfileScreen(page: ft.Page, device_id: str, session=None):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    name, set_name = ft.use_state(state.username)
    dialog, set_dialog = ft.use_state(False)
    error, set_error = ft.use_state("")
    icons_open, set_icons_open = ft.use_state(False)
    from collection_progress import ensure
    from cosmetic_catalog import cosmetic_name

    cosmetics = ensure(state)

    def set_emblem(identity):
        async def run(_):
            session.act("emblem_equip", identity)

        return run

    async def toggle_icons(_):
        set_icons_open(lambda value: not value)

    if not state.robot_levels:
        rest_status = "После открытия робот заряжается и во время отдыха"
    elif all(
        state.robot_energy.get(identity, 70) >= 100 for identity in state.robot_levels
    ):
        rest_status = "Команда заряжена · можно выйти на арену"
    else:
        rest_status = f"Отдых заряжает команду · +1 через {max(1, 45 - int(state.robot_charge_carry))} с"

    async def save_name(_):
        result = session.act("rename", name)
        if result.ok:
            set_dialog(False)
            set_error("")
        else:
            set_error(result.message)

    async def open_name(_):
        set_name(state.username)
        set_error("")
        set_dialog(True)

    async def close_name(_):
        set_dialog(False)

    ft.use_dialog(
        ft.AlertDialog(
            title=ft.Text("Имя твоей мастерской"),
            content=ft.Column(
                [
                    ft.Text("Изменение имени стоит 500 игровых монет", size=12),
                    ft.TextField(
                        label="От 2 до 20 символов",
                        value=name,
                        max_length=20,
                        on_change=lambda event: set_name(event.control.value),
                    ),
                    ft.Text(error, color="#B95555", size=12),
                ],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=close_name),
                ft.Button(
                    "Сохранить",
                    on_click=save_name,
                    disabled=state.coin < 500,
                    style=button_style(state.accent),
                ),
            ],
        )
        if dialog
        else None
    )

    palette = []
    for index, color in enumerate(PALETTES):

        async def choose_color(_, selected=color):
            if not session.ui_alive:
                return
            session.act("theme", selected)
            page.theme = ft.Theme(color_scheme_seed=selected)
            page.bgcolor = tint(selected, 0.94)
            if callable(getattr(page, "update", None)):
                page.update()

        palette.append(
            ft.Container(
                content=ft.Icon(
                    ft.Icons.CHECK_ROUNDED
                    if state.accent == color
                    else ft.Icons.PALETTE_OUTLINED,
                    size=21,
                    color="white",
                ),
                bgcolor=color,
                width=45,
                height=45,
                border_radius=15,
                alignment=ft.Alignment.CENTER,
                on_click=choose_color,
                key=f"theme-{index}",
            )
        )

    worlds = []
    for index, stage in enumerate(STAGES):
        unlocked = state.level >= stage.level
        worlds.append(
            card(
                ft.Column(
                    [
                        ft.Image(
                            f"art/room_{index}.webp",
                            height=65,
                            cache_width=240,
                            fit=ft.BoxFit.COVER,
                            border_radius=12,
                        ),
                        ft.Container(
                            ft.Text(
                                stage.title,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                                max_lines=2,
                            ),
                            height=32,
                        ),
                        ft.Text(
                            "Открыто" if unlocked else f"С уровня {stage.level}",
                            size=10,
                            color=state.accent if unlocked else MUTED,
                        ),
                    ],
                    spacing=6,
                ),
                padding=9,
                col=4,
                opacity=1 if unlocked else 0.46,
            )
        )

    return ft.Column(
        [
            heading("Твоя мастерская", "Команда, открытия и твой стиль", wallet(state)),
            card(
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Image(
                                selected_avatar(state).image,
                                width=65,
                                height=72,
                                cache_width=144,
                            ),
                            bgcolor=tint(state.accent, 0.86),
                            padding=9,
                            border_radius=22,
                            on_click=toggle_icons,
                            tooltip="Выбрать иконку профиля",
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    state.username or "Исследователь",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=INK,
                                ),
                                ft.Text(state.stage.title, size=13, color=state.accent),
                                ft.Text(
                                    f"Уровень {state.level} · {compact(state.manual_taps)} касаний",
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                        *(
                            [
                                robot_actor(
                                    state.active_robot, size=54, now=session.clock()
                                )
                            ]
                            if state.active_robot
                            else []
                        ),
                    ],
                    spacing=14,
                ),
                gradient=page_gradient(state.accent),
            ),
            notice(session),
            ft.TextButton(
                "Скрыть иконки" if icons_open else "Выбрать иконку профиля",
                icon=ft.Icons.BADGE_OUTLINED,
                on_click=toggle_icons,
                key="profile-icons-toggle",
            ),
            avatar_picker(session) if icons_open else ft.Container(height=0),
            *(
                [
                    card(
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        badge("arena", 30),
                                        ft.Text(
                                            cosmetic_name(
                                                "emblem", cosmetics["selected_emblem"]
                                            )
                                            if cosmetics["selected_emblem"]
                                            else "Сезонные эмблемы",
                                            color=GOLD,
                                            size=13,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Row(
                                    [
                                        ft.TextButton(
                                            cosmetic_name("emblem", item),
                                            on_click=set_emblem(item),
                                        )
                                        for item in cosmetics["emblems"]
                                    ],
                                    wrap=True,
                                    spacing=5,
                                ),
                            ],
                            spacing=8,
                        )
                    )
                ]
                if cosmetics["emblems"]
                else []
            ),
            AdDiagnostics(page=page),
            project_gallery(session),
            card(
                ft.Row(
                    [
                        badge("clock", 42),
                        ft.Column(
                            [
                                ft.Text(
                                    f"Вместе {int(state.play_seconds) // 3600:02d}:{int(state.play_seconds) // 60 % 60:02d}:{int(state.play_seconds) % 60:02d}",
                                    size=15,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    rest_status,
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                ),
                bgcolor=tint(state.accent, 0.94),
            ),
            card(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=28),
                        ft.Column(
                            [
                                ft.Text(
                                    f"{len(state.claimed_goals)} / {len(GOALS)} целей выполнено",
                                    size=14,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"Роботов: {state.robot_count} / {len(ROBOTS)} · Заказов: {state.jobs_done}",
                                    size=12,
                                    color=MUTED,
                                ),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                )
            ),
            ft.Text(
                "Твоя коллекция миров", size=16, weight=ft.FontWeight.BOLD, color=INK
            ),
            ft.ResponsiveRow(worlds, columns=12, spacing=8, run_spacing=8),
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.PALETTE_ROUNDED,
                                    color=state.accent,
                                    size=23,
                                ),
                                ft.Text(
                                    "Атмосфера мастерской",
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                    color=INK,
                                ),
                            ],
                            spacing=9,
                        ),
                        ft.Text(
                            "Твой цвет в фоне, карточках, меню и кнопках",
                            size=11,
                            color=MUTED,
                        ),
                        ft.Row(palette, spacing=12),
                    ],
                    spacing=13,
                )
            ),
            ft.Button(
                "Изменить имя · 500 монет",
                icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
                on_click=open_name,
                disabled=not session.trusted or state.coin < 500,
                style=button_style(state.accent, secondary=True),
                width=float("inf"),
            ),
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                badge("profile", 25),
                                ft.Text(
                                    "Сохранение",
                                    size=14,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=8,
                        ),
                        saving_status(session),
                        ft.Text("ID игрока", size=10, color=MUTED),
                        ft.Text(
                            session.device_id or "Открываем сохранение…",
                            size=10,
                            color=MUTED,
                            selectable=True,
                        ),
                    ],
                    spacing=7,
                )
            ),
        ],
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def profile_screen(page: ft.Page, device_id: str, session=None):
    return ProfileScreen(page=page, device_id=device_id, session=session)
