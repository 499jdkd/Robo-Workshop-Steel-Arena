"""Network screens: every player, match, clan and reward comes from the server."""

import asyncio
import flet as ft

from battle_ui import battle_scene
from combat_rules import action_error, allowed
from game_ui import game_button, tabs
from network_config import developer_network
from online_arena import online_for
from ui_shared import GOLD, GREEN, INK, MUTED, button_style, card, use_game

from combat_info import ACTION_TITLES, action_control


def online_actions(online, command):
    match = online.match
    if not match or match["result"] != "active":
        return []
    side = match["you"]
    actor = match["state"][side]
    target = match["state"]["b" if side == "a" else "a"]
    blocked = "Роботы выполняют ход…" if online.busy else "Ход соперника" if match["state"]["turn"] != side else ""
    return [action_control(actor, action, command(action), online.session.state.accent,
                           target=target, blocked=blocked, key=f"online-{action}")
            for action in ACTION_TITLES if action in allowed(actor)]


@ft.component
def OnlineScreen(page, session, clans=False, ranking=False):
    use_game(session)
    online = online_for(session)
    address, set_address = ft.use_state(online.url)
    clan_name, set_clan_name = ft.use_state("")
    description, set_description = ft.use_state("")
    emblem, set_emblem = ft.use_state("gear")
    search, set_search = ft.use_state("")
    code, set_code = ft.use_state("")
    friend, set_friend = ft.use_state("")
    selected_tab, set_tab = ft.use_state(0)
    tab = 3 if ranking else selected_tab

    def mounted():
        async def poll():
            if online.url and not online.profile and not online.started:
                online.started = True
                await online.connect(online.url, session.state.username)
            while session.ui_alive:
                await asyncio.sleep(2)
                await online.refresh()

        task = page.run_task(poll)
        return lambda: task.cancel() if task is not None else None

    ft.use_effect(mounted, [])

    async def connect(_):
        await online.connect(address or online.url, session.state.username)

    def command(name, value=""):
        async def run(_):
            await online.command(name, value)

        return run

    rows = []
    if online.error:
        rows.append(card(ft.Text(online.error, color="#FFC1B0", size=12)))
    if not online.profile:
        rows.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            "Кланы и сетевая арена",
                            size=20,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Подключаемся к серверу игры…"
                            if online.busy
                            else "Онлайн временно недоступен"
                            if online.url
                            else "Сервер ещё не подключён к этой сборке",
                            color=GOLD,
                            size=13,
                        ),
                        ft.Text(
                            "PvP использует настоящих игроков. Пока можно сражаться с ботами во вкладке «Арены»; они явно отмечены как тренеры.",
                            size=12,
                            color=MUTED,
                        ),
                        *(
                            [
                                ft.TextField(
                                    value=address,
                                    label="Адрес сервера · режим разработчика",
                                    on_change=lambda e: set_address(e.control.value),
                                    text_size=12,
                                )
                            ]
                            if developer_network()
                            else []
                        ),
                        *(
                            [
                                game_button(
                                    "Повторить подключение",
                                    connect,
                                    key="online-connect",
                                    disabled=online.busy,
                                )
                            ]
                            if online.url or developer_network()
                            else []
                        ),
                    ],
                    spacing=12,
                ),
                key="network-status",
            )
        )
        return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    if clans:
        records = online.clans
        own = records.get("your_clan")
        own_record = next(
            (item for item in records.get("clans", []) if item["id"] == own), {}
        )
        is_owner = own_record.get("owner") == online.profile["id"]
        controls = [
            ft.Text("Кланы мастерских", size=20, color=INK, weight=ft.FontWeight.BOLD),
            ft.Text(
                f"PvP-жетоны: {online.profile['coins']} · общая цель: 20 рейтинговых побед за неделю",
                size=11,
                color=MUTED,
            ),
            ft.TextField(
                label="Поиск по названию",
                value=search,
                on_change=lambda e: set_search(e.control.value),
            ),
            ft.TextButton(
                "Найти клан",
                on_click=command("clan_search", search),
                disabled=online.busy,
            ),
        ]
        if not own:
            controls.extend(
                [
                    ft.TextField(
                        label="Название нового клана",
                        value=clan_name,
                        max_length=24,
                        on_change=lambda e: set_clan_name(e.control.value),
                    ),
                    game_button(
                        "Создать · 50 жетонов",
                        command("create", clan_name),
                        disabled=online.busy,
                    ),
                ]
            )
        else:
            controls.extend(
                [
                    ft.Row(
                        [
                            ft.Button(
                                "Вклад · 10",
                                on_click=command("donate"),
                                disabled=online.busy,
                            ),
                            ft.Button(
                                "Награда недели",
                                on_click=command("mission"),
                                disabled=online.busy,
                            ),
                        ],
                        wrap=True,
                        spacing=6,
                    ),
                    ft.TextButton(
                        "Выйти из клана",
                        on_click=command("leave"),
                        disabled=online.busy,
                    ),
                ]
            )
            if is_owner:
                controls.extend(
                    [
                        ft.TextField(
                            label="Описание клана",
                            value=description,
                            max_length=160,
                            on_change=lambda e: set_description(e.control.value),
                        ),
                        ft.Dropdown(
                            label="Эмблема",
                            value=emblem,
                            options=[
                                ft.DropdownOption(k, v)
                                for k, v in [
                                    ("gear", "Шестерня"),
                                    ("shield", "Щит"),
                                    ("bolt", "Молния"),
                                    ("star", "Звезда"),
                                    ("leaf", "Лист"),
                                ]
                            ],
                            on_select=lambda e: set_emblem(e.control.value),
                        ),
                        game_button(
                            "Сохранить описание и эмблему",
                            command("edit", description + "|" + emblem),
                            kind="blue",
                            disabled=online.busy,
                        ),
                    ]
                )
        rows.append(card(ft.Column(controls, spacing=10)))
        icons = {
            "gear": ft.Icons.SETTINGS_ROUNDED,
            "shield": ft.Icons.SHIELD_ROUNDED,
            "bolt": ft.Icons.BOLT_ROUNDED,
            "star": ft.Icons.STAR_ROUNDED,
            "leaf": ft.Icons.ECO_ROUNDED,
        }
        for clan in records.get("clans", []):
            body = [
                ft.Row(
                    [
                        ft.Icon(
                            icons.get(clan.get("emblem"), ft.Icons.SETTINGS_ROUNDED),
                            color=GOLD,
                            size=30,
                        ),
                        ft.Text(
                            clan["name"]
                            + (" · твой клан" if clan["id"] == own else ""),
                            color=INK,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    clan.get("description") or "Мастерская ищет единомышленников",
                    color=MUTED,
                    size=11,
                ),
                ft.Text(
                    f"Уровень {clan['level']} · {clan['members']}/30 участников · рейтинг {clan['rating']}",
                    color=MUTED,
                    size=11,
                ),
                ft.ProgressBar(value=min(1, clan["mission_wins"] / 20), color=GREEN),
                ft.Text(
                    f"Задание недели: {clan['mission_wins']}/20 побед",
                    color=GOLD,
                    size=11,
                ),
            ]
            if not own:
                body.append(
                    game_button(
                        "Вступить",
                        command("join", clan["id"]),
                        kind="blue",
                        disabled=online.busy,
                    )
                )
            elif clan["id"] != own and is_owner:
                body.append(
                    ft.Button(
                        "Клановая война",
                        on_click=command("war", clan["id"]),
                        disabled=online.busy,
                    )
                )
            for member in clan.get("roster", []):
                body.append(
                    ft.Text(
                        member["name"]
                        + " · "
                        + {"owner": "Глава", "officer": "Офицер", "member": "Участник"}[
                            member["role"]
                        ],
                        color=INK,
                        size=12,
                    )
                )
                if is_owner and member["id"] != online.profile["id"]:
                    body.append(
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Понизить"
                                    if member["role"] == "officer"
                                    else "Повысить",
                                    on_click=command(
                                        "demote"
                                        if member["role"] == "officer"
                                        else "promote",
                                        member["id"],
                                    ),
                                ),
                                ft.TextButton(
                                    "Исключить", on_click=command("kick", member["id"])
                                ),
                            ],
                            wrap=True,
                            spacing=4,
                        )
                    )
            rows.append(card(ft.Column(body, spacing=9)))
        names = {c["id"]: c["name"] for c in records.get("clans", [])}
        for war in records.get("wars", []):
            body = [
                ft.Text(
                    f"{names.get(war['a'], 'Клан')} — {names.get(war['b'], 'Клан')}",
                    color=INK,
                    size=14,
                ),
                ft.Text(
                    f"Война недели · {war['score_a']} : {war['score_b']}",
                    color=GOLD,
                    size=12,
                ),
                ft.Text(
                    "В зачёт идут подтверждённые сервером рейтинговые победы между этими кланами.",
                    color=MUTED,
                    size=11,
                ),
            ]
            if war["week"] < records.get("week", 0):
                body.append(
                    ft.Button(
                        "Награда войны · 40",
                        on_click=command("war_claim", war["id"]),
                        disabled=online.busy,
                    )
                )
            rows.append(card(ft.Column(body, spacing=8)))
    else:
        rows.append(tabs(["Бои", "Друзья", "История", "Рейтинг"], tab, set_tab))
        if tab == 0:
            league = online.profile.get("league", {})
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Text(
                                f"{league.get('name', 'Лига')} {league.get('division', '')} · {online.profile['rating']}",
                                color=GOLD,
                                size=20,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Равные уровни и базовое оружие. Класс и контрприёмы сохраняются; локальные покупки не повышают характеристики. Подбор учитывает рейтинг и расчётную силу сборки.",
                                color=MUTED,
                                size=11,
                            ),
                            ft.Dropdown(
                                label="Режим",
                                value=online.mode,
                                options=[
                                    ft.DropdownOption("ranked", "Рейтинговый"),
                                    ft.DropdownOption(
                                        "balanced", "Сбалансированная практика"
                                    ),
                                ],
                                on_select=lambda e: set_mode(online, e.control.value),
                                disabled=online.waiting,
                            ),
                            game_button(
                                "Отменить поиск"
                                if online.waiting
                                else "Найти реального игрока",
                                command("cancel" if online.waiting else "queue"),
                                key="pvp-find",
                                disabled=online.busy,
                            ),
                            *(
                                [
                                    ft.Text(
                                        "Ожидаем игрока. Боты не подменяют людей.",
                                        color=MUTED,
                                        size=11,
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
                active = match["result"] == "active"
                actor = match["state"][side]
                rows.extend(
                    [
                        ft.Text(
                            "Реальный игрок: " + match["players"][other]["name"],
                            color=INK,
                            size=13,
                        ),
                        battle_scene(page, session, online.view_battle()),
                        ft.Text(
                            "Твой ход"
                            if active and match["state"]["turn"] == side
                            else "Ход соперника"
                            if active
                            else "Матч завершён сервером",
                            color=GOLD,
                            size=13,
                        ),
                    ]
                )
                if active:
                    rows.extend(
                        [
                            ft.Text(
                                f"Энергия {actor['energy']}/{actor['max_energy']} · Супер {actor['super_charge']}% · На ход 45 секунд",
                                color=MUTED,
                                size=11,
                            ),
                            ft.ResponsiveRow(
                                online_actions(online, command),
                                spacing=6,
                                run_spacing=6,
                            ),
                            ft.TextButton(
                                "Сдаться",
                                on_click=command("resign"),
                                disabled=online.busy,
                            ),
                        ]
                    )
        elif tab == 1:
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Text("Твой код игрока", color=MUTED, size=11),
                            ft.Text(
                                online.profile["id"],
                                selectable=True,
                                color=GOLD,
                                size=11,
                            ),
                            ft.TextField(
                                label="Код друга",
                                value=friend,
                                max_length=24,
                                on_change=lambda e: set_friend(e.control.value),
                            ),
                            game_button(
                                "Пригласить в друзья",
                                command("friend_request", friend),
                                disabled=online.busy,
                            ),
                            game_button(
                                "Создать дуэль по коду",
                                command("duel_create"),
                                kind="blue",
                                disabled=online.busy,
                            ),
                            *(
                                [
                                    ft.Text(
                                        "Код дуэли: "
                                        + online.invitation["code"]
                                        + " · действует 10 минут",
                                        selectable=True,
                                        color=GOLD,
                                        size=15,
                                    )
                                ]
                                if online.invitation
                                else []
                            ),
                            ft.TextField(
                                label="Код дуэли",
                                value=code,
                                max_length=8,
                                on_change=lambda e: set_code(e.control.value),
                            ),
                            game_button(
                                "Присоединиться к дуэли",
                                command("duel_join", code),
                                kind="green",
                                disabled=online.busy,
                            ),
                            ft.Text(
                                "Дружеские дуэли не начисляют рейтинг, жетоны и клановые очки.",
                                size=11,
                                color=MUTED,
                            ),
                        ],
                        spacing=10,
                    )
                )
            )
            for record in online.friends:
                body = [
                    ft.Text(
                        record["name"] + " · " + str(record["rating"]),
                        color=INK,
                        size=14,
                    ),
                    ft.Text(
                        "В друзьях"
                        if record["status"] == "accepted"
                        else "Приглашение отправлено"
                        if record["requester"] == online.profile["id"]
                        else "Входящее приглашение",
                        color=MUTED,
                        size=11,
                    ),
                ]
                if (
                    record["status"] == "pending"
                    and record["requester"] != online.profile["id"]
                ):
                    body.append(
                        ft.Button(
                            "Принять",
                            on_click=command("friend_accept", record["id"]),
                            disabled=online.busy,
                        )
                    )
                body.append(
                    ft.TextButton(
                        "Удалить",
                        on_click=command("friend_remove", record["id"]),
                        disabled=online.busy,
                    )
                )
                rows.append(card(ft.Column(body, spacing=7)))
        elif tab == 2:
            if not online.history:
                rows.append(
                    card(
                        ft.Text(
                            "Завершённых сетевых матчей пока нет", color=MUTED, size=12
                        )
                    )
                )
            for match in online.history:
                rows.append(
                    card(
                        ft.Column(
                            [
                                ft.Text(
                                    (
                                        "Ничья"
                                        if match.get("draw")
                                        else "Победа"
                                        if match["won"]
                                        else "Поражение"
                                    )
                                    + " · "
                                    + match["opponent"],
                                    color=GREEN if match["won"] else "#FFB2AE",
                                    size=14,
                                ),
                                ft.Text(
                                    f"{match['mode']} · {match['turns']} ходов · {match['reason']}",
                                    color=MUTED,
                                    size=11,
                                ),
                            ],
                            spacing=6,
                        )
                    )
                )
        else:
            rows.append(
                ft.Text(
                    "Рейтинг настоящих игроков",
                    color=INK,
                    size=19,
                    weight=ft.FontWeight.BOLD,
                )
            )
            for n, player in enumerate(online.ranking):
                rows.append(
                    card(
                        ft.Row(
                            [
                                ft.Text(str(n + 1), color=GOLD),
                                ft.Text(player["name"], color=INK, expand=True),
                                ft.Text(str(player["rating"]), color=GOLD),
                                ft.IconButton(
                                    ft.Icons.PERSON_ADD_ROUNDED,
                                    on_click=command("friend_request", player["id"]),
                                    disabled=online.busy
                                    or player["id"] == online.profile["id"],
                                ),
                            ],
                            spacing=7,
                        ),
                        padding=9,
                    )
                )
    return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


def set_mode(online, value):
    online.mode = value
    online.notify()
