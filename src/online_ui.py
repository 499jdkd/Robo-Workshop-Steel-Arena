"""Human opponents and clan records are always supplied by the server."""

import asyncio

import flet as ft

from battle_ui import battle_scene
from online_arena import online_for
from ui_shared import INK, MUTED, button_style, card, use_game


@ft.component
def OnlineScreen(page, session, clans=False):
    use_game(session)
    online = online_for(session)
    address, set_address = ft.use_state(online.url)
    clan_name, set_clan_name = ft.use_state("")

    def mounted():
        async def poll():
            while session.ui_alive:
                await asyncio.sleep(2)
                await online.refresh()

        task = page.run_task(poll)
        return lambda: task.cancel() if task is not None else None

    ft.use_effect(mounted, [])

    async def connect(_):
        await online.connect(address, session.state.username)

    def command(name, value=""):
        async def run(_):
            await online.command(name, value)

        return run

    rows = []
    if online.error:
        rows.append(card(ft.Text(online.error, color="#AE5864", size=12)))
    if not online.profile:
        rows.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            "Кланы и рейтинговая арена",
                            size=19,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Подключись к игровому серверу. В PvP участвуют только люди. Локальные бои с ботами доступны во вкладке «Арены».",
                            size=12,
                            color=MUTED,
                        ),
                        ft.TextField(
                            value=address,
                            label="Адрес сервера",
                            on_change=lambda e: set_address(e.control.value),
                            text_size=12,
                        ),
                        ft.Button(
                            "Подключиться",
                            key="online-connect",
                            on_click=connect,
                            disabled=online.busy,
                            style=button_style(session.state.accent),
                        ),
                    ],
                    spacing=10,
                )
            )
        )
    elif clans:
        records = online.clans
        own = records.get("your_clan")
        rows.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            "Твой клан", size=19, color=INK, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            f"PvP-жетоны: {online.profile['coins']} · Награды хранятся на сервере",
                            size=11,
                            color=MUTED,
                        ),
                        ft.Text(
                            "20 общих рейтинговых побед недели открывают награду участникам. Для получения нужна хотя бы одна личная победа.",
                            size=12,
                            color=MUTED,
                        ),
                        *(
                            [
                                ft.TextField(
                                    label="Название нового клана",
                                    value=clan_name,
                                    on_change=lambda e: set_clan_name(e.control.value),
                                ),
                                ft.Button(
                                    "Создать · 50 жетонов",
                                    on_click=command("create", clan_name),
                                    disabled=online.busy,
                                    style=button_style(session.state.accent),
                                ),
                            ]
                            if not own
                            else [
                                ft.Row(
                                    [
                                        ft.Button(
                                            "Вклад · 10 жетонов",
                                            on_click=command("donate"),
                                            disabled=online.busy,
                                        ),
                                        ft.Button(
                                            "Награда",
                                            on_click=command("mission"),
                                            disabled=online.busy,
                                        ),
                                    ],
                                    spacing=6,
                                    wrap=True,
                                ),
                                ft.Button(
                                    "Выйти из клана",
                                    on_click=command("leave"),
                                    disabled=online.busy,
                                ),
                            ]
                        ),
                    ],
                    spacing=10,
                )
            )
        )
        for clan in records.get("clans", []):
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Text(
                                clan["name"]
                                + (" · твой клан" if clan["id"] == own else ""),
                                size=17,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"Уровень {clan['level']} · Опыт {clan['xp']} · {clan['members']}/30 участников",
                                size=12,
                                color=MUTED,
                            ),
                            ft.ProgressBar(
                                value=min(1, clan["mission_wins"] / 20),
                                color=session.state.accent,
                            ),
                            ft.Text(
                                f"Задание недели: {clan['mission_wins']}/20 побед",
                                size=11,
                                color=MUTED,
                            ),
                            *(
                                [
                                    ft.Button(
                                        "Вступить",
                                        on_click=command("join", clan["id"]),
                                        disabled=online.busy,
                                    )
                                ]
                                if not own
                                else [
                                    ft.Button(
                                        "Начать клановую войну",
                                        on_click=command("war", clan["id"]),
                                        disabled=online.busy,
                                    )
                                ]
                                if clan["id"] != own
                                else []
                            ),
                        ],
                        spacing=8,
                    )
                )
            )
        names = {c["id"]: c["name"] for c in records.get("clans", [])}
        for war in records.get("wars", []):
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Text(
                                f"{names.get(war['a'], 'Клан')} — {names.get(war['b'], 'Клан')}",
                                size=15,
                                color=INK,
                            ),
                            ft.Text(
                                f"Война недели · {war['score_a']} : {war['score_b']}",
                                color=session.state.accent,
                            ),
                            ft.Text(
                                "В зачёт идут настоящие рейтинговые матчи участников этих кланов.",
                                size=11,
                                color=MUTED,
                            ),
                            *(
                                [
                                    ft.Button(
                                        "Награда войны · 40 жетонов",
                                        on_click=command("war_claim", war["id"]),
                                        disabled=online.busy,
                                    )
                                ]
                                if war["week"] < records.get("week", 0)
                                else []
                            ),
                        ],
                        spacing=7,
                    )
                )
            )
    else:
        rows.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            f"Рейтинговая арена · {online.profile['rating']}",
                            size=19,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Равные уровни и базовые версии оружия. Прогресс мастерской сохраняется отдельно. Победа: +16 рейтинга и 25 жетонов.",
                            size=12,
                            color=MUTED,
                        ),
                        ft.Button(
                            "Отменить поиск"
                            if online.waiting
                            else "Найти реального игрока",
                            key="pvp-find",
                            on_click=command("cancel" if online.waiting else "queue"),
                            disabled=online.busy,
                            style=button_style(session.state.accent),
                        ),
                        *(
                            [
                                ft.Text(
                                    "Ожидаем игрока. Боты не подменяют людей.",
                                    color=MUTED,
                                    size=12,
                                )
                            ]
                            if online.waiting
                            else []
                        ),
                    ],
                    spacing=10,
                )
            )
        )
        match = online.match
        if match:
            side = match["you"]
            other = "b" if side == "a" else "a"
            rows.append(
                card(
                    ft.Text(
                        f"Реальный игрок: {match['players'][other]['name']} · рейтинг {match['players'][other]['rating']}",
                        size=13,
                        color=INK,
                    )
                )
            )
            rows.append(battle_scene(page, session, online.view_battle()))
            your_turn = match["result"] == "active" and match["state"]["turn"] == side
            rows.append(
                ft.Text(
                    "Твой ход"
                    if your_turn
                    else "Ход соперника"
                    if match["result"] == "active"
                    else "Матч завершён; результат подтверждён сервером",
                    color=session.state.accent,
                    size=13,
                )
            )
            if match["result"] == "active":
                rows.append(
                    ft.Text(
                        f"Энергия: {match['state'][side]['energy']}/10 · На ход 45 секунд",
                        color=MUTED,
                        size=11,
                    )
                )
                rows.append(
                    ft.ResponsiveRow(
                        [
                            ft.Button(
                                title,
                                on_click=command(action),
                                disabled=online.busy or not your_turn,
                                style=button_style(
                                    session.state.accent, secondary=action != "attack"
                                ),
                                col=6,
                            )
                            for action, title in [
                                ("attack", "Атака"),
                                ("guard", "Защита"),
                                ("special", "Способность"),
                                ("dodge", "Уклонение"),
                                ("charge", "Зарядка"),
                            ]
                        ],
                        spacing=6,
                        run_spacing=6,
                    )
                )
                rows.append(
                    ft.Button(
                        "Сдаться", on_click=command("resign"), disabled=online.busy
                    )
                )
        rows.append(
            ft.Text(
                "Рейтинг настоящих игроков",
                size=17,
                color=INK,
                weight=ft.FontWeight.BOLD,
            )
        )
        for index, player in enumerate(online.ranking[:20]):
            rows.append(
                card(
                    ft.Row(
                        [
                            ft.Text(str(index + 1), color=MUTED),
                            ft.Text(player["name"], expand=True, color=INK),
                            ft.Text(str(player["rating"]), color=session.state.accent),
                        ],
                        spacing=9,
                    ),
                    padding=12,
                )
            )
    return ft.Column(rows, scroll=ft.ScrollMode.AUTO, expand=True, spacing=11)
