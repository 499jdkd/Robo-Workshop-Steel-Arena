import flet as ft

from game_session import preview_session
from gameplay import compact, number
from ui_shared import (
    GOLD,
    INK,
    MUTED,
    button_style,
    card,
    heading,
    saving_status,
    use_game,
)


@ft.component
def LeaderboardScreen(page: ft.Page, device_id: str, session=None):
    session = session or preview_session(page, device_id)
    state = use_game(session)

    async def start_load():
        await session.refresh_board()

    ft.use_effect(start_load, [session])

    async def refresh(_):
        await session.refresh_board(force=True)

    controls = [
        heading("Лига мастеров", "У каждого большое открытие впереди"),
        card(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.EMOJI_EVENTS_ROUNDED, color=GOLD, size=31
                        ),
                        bgcolor="#FFF1CD",
                        padding=13,
                        border_radius=18,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                f"Твой уровень: {state.level}",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                            ),
                            ft.Text(
                                f"{compact(state.session_taps)} очков в мастерской",
                                size=12,
                                color=MUTED,
                            ),
                            saving_status(session),
                        ],
                        spacing=6,
                        expand=True,
                    ),
                ],
                spacing=13,
            )
        ),
        ft.Row(
            [
                ft.Text(
                    "Пять лучших мастерских",
                    size=16,
                    color=INK,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                ),
                ft.Button(
                    "Обновить",
                    key="leaderboard-refresh",
                    on_click=refresh,
                    disabled=session.board_loading,
                    style=button_style(state.accent, secondary=True),
                ),
            ]
        ),
    ]
    if session.board_loading and not session.board:
        controls.append(
            card(
                ft.Row(
                    [
                        ft.ProgressRing(
                            width=22, height=22, stroke_width=3, color=state.accent
                        ),
                        ft.Text("Собираем результаты…", size=13, color=MUTED),
                    ],
                    spacing=12,
                )
            )
        )
    elif session.board_error:
        controls.append(
            card(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, color=MUTED),
                        ft.Text(
                            (
                                session.board_error_detail
                                or "Сейчас рейтинг не обновился. Можно продолжать игру и попробовать позже."
                            )
                            + (
                                " Ниже — последние сохранённые результаты."
                                if session.board
                                else ""
                            ),
                            color=MUTED,
                            size=12,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
                bgcolor="#EDF1F8",
            )
        )
    elif session.board_loaded and not session.board:
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.ROCKET_LAUNCH_ROUNDED, color=state.accent, size=34
                        ),
                        ft.Text(
                            "Первая мастерская может стать твоей",
                            size=16,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Собирай монеты, открывай уровни и возвращайся за результатами",
                            size=12,
                            color=MUTED,
                        ),
                    ],
                    spacing=9,
                ),
                padding=20,
            )
        )

    for index, player in enumerate(session.board):
        name = str(
            player.get("username") or f"Мастер {str(player.get('id', 'новичок'))[:5]}"
        )[:24]
        controls.append(
            card(
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(
                                str(index + 1),
                                size=20,
                                color="#B48223" if index == 0 else state.accent,
                                weight=ft.FontWeight.BOLD,
                            ),
                            width=44,
                            height=44,
                            bgcolor="#FFF1CD" if index == 0 else "#EDF1FC",
                            border_radius=15,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    name, size=15, color=INK, weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    f"{compact(number(player.get('taps')))} очков",
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"Ур. {number(player.get('level'), 1)}",
                                size=12,
                                color=state.accent,
                                weight=ft.FontWeight.BOLD,
                            ),
                            padding=9,
                            bgcolor="#EFF3FD",
                            border_radius=10,
                        ),
                    ],
                    spacing=12,
                ),
                padding=13,
            )
        )
    return ft.Column(
        controls=controls, spacing=14, scroll=ft.ScrollMode.AUTO, expand=True
    )


def leaderboard_screen(page: ft.Page, device_id: str, session=None):
    return LeaderboardScreen(page=page, device_id=device_id, session=session)
