"""Arena route, animated tactical duels and a separate asynchronous ranking."""

import flet as ft

from armory_ui import arena_options

from battle_ui import animate_turn, battle_scene
from display_mode import set_arena_expanded
from game_session import preview_session
from leaderboard_screen import LeaderboardScreen
from online_ui import OnlineScreen
from robot_arena import (
    BATTLE_ENERGY,
    ELEMENT_NAMES,
    ELEMENTS,
    INTENT_NAMES,
    SPECIALS,
    element_multiplier,
    enemy_for,
    enemy_intent,
    league_name,
    new_battle,
    robot_stats,
    suggested_action,
)
from robot_care_ui import care_panel, food_bar
from robot_catalog import ROBOTS
from robot_motion import robot_actor
from ui_shared import (
    GOLD,
    GREEN,
    INK,
    MUTED,
    badge,
    button_style,
    card,
    heading,
    notice,
    tint,
    use_game,
)


def route_map(state):
    start = state.arena_stage // 5 * 5
    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        badge("arena", 30),
                        ft.Text(
                            league_name(state.arena_stage),
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            expand=True,
                        ),
                        ft.Text(f"Побед: {state.arena_wins}", size=10, color=MUTED),
                    ]
                ),
                ft.Row(
                    [
                        ft.Container(
                            ft.Column(
                                [
                                    ft.Icon(
                                        ft.Icons.EMOJI_EVENTS_ROUNDED
                                        if i < state.arena_stage
                                        else ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED
                                        if i % 5 == 4
                                        else ft.Icons.LOCATION_ON_ROUNDED
                                        if i == state.arena_stage
                                        else ft.Icons.LOCK_ROUNDED,
                                        size=23,
                                        color="white"
                                        if i == state.arena_stage
                                        else GOLD
                                        if i < state.arena_stage
                                        else MUTED,
                                    ),
                                    ft.Text(
                                        "Страж" if i % 5 == 4 else str(i + 1),
                                        size=10,
                                        color="white"
                                        if i == state.arena_stage
                                        else INK,
                                    ),
                                ],
                                spacing=4,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=9,
                            bgcolor=state.accent
                            if i == state.arena_stage
                            else tint(state.accent, 0.94),
                            border_radius=14,
                            expand=True,
                        )
                        for i in range(start, start + 5)
                    ],
                    spacing=6,
                ),
                ft.Text(
                    "Каждый пятый соперник — страж. Следующая лига сложнее предыдущей.",
                    size=10,
                    color=MUTED,
                ),
            ],
            spacing=11,
        ),
        padding=13,
    )


def hints_tooltip(action):
    return {
        "attack": "Урон и +1 фокус; чередуй действия, чтобы не перегреваться",
        "guard": "Снижает ответный урон и восстанавливает фокус",
        "dodge": "1 фокус; избегает рывка и луча, но не энергокольца",
        "charge": "+2 фокуса и усиление следующей атаки",
    }.get(action, "")


@ft.component
def BattleHelp(session):
    opened, set_opened = ft.use_state(False)
    battle = session.state.battle
    special = SPECIALS.get(battle.get("robot_id", "spark"), SPECIALS["spark"])

    async def show(_):
        set_opened(True)

    async def close(_):
        set_opened(False)
        session.act("tutorial_done")

    ft.use_dialog(
        ft.AlertDialog(
            title=ft.Text("Как сражаться", size=20),
            content=ft.Column(
                [
                    ft.Text(
                        "Смотри намерение над кнопками: соперник заранее показывает следующий ответ.",
                        size=13,
                        color=INK,
                    ),
                    ft.Text(
                        "Удар: урон и +1 фокус. Три удара подряд перегревают мотор.",
                        size=12,
                        color=INK,
                    ),
                    ft.Text(
                        "Щит: снижает урон и даёт фокус. Уворот: 1 фокус, избегает рывка и луча.",
                        size=12,
                        color=INK,
                    ),
                    ft.Text(
                        "Против энергокольца нужен щит. Фокус усиливает следующий удар.",
                        size=12,
                        color=INK,
                    ),
                    ft.Text(
                        f"Твой навык — {special[0]}",
                        size=14,
                        color=session.state.accent,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        special[1]
                        + ". Требуется 2 фокуса; затем два промежуточных хода перезарядки.",
                        size=12,
                        color=INK,
                    ),
                    ft.Text(
                        "Снаряд летит около секунды. Дождись ответа роботов перед следующим ходом.",
                        size=11,
                        color=MUTED,
                    ),
                ],
                spacing=12,
                tight=True,
                width=300,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[ft.TextButton("Понятно", on_click=close)],
            on_dismiss=close,
        )
        if opened
        else None
    )
    return ft.IconButton(
        icon=ft.Icons.HELP_OUTLINE_ROUNDED,
        tooltip="Как играть",
        on_click=show,
        key="arena-help",
    )


def action_panel(session, *, wide=False):
    battle, state = session.state.battle, session.state
    identity, turn = battle["id"], battle["turn"]
    active = battle["result"] == "active"
    busy = session.arena_animating
    buttons = []
    choices = [
        ("attack", "Удар", ft.Icons.BOLT_ROUNDED),
        ("guard", "Щит", ft.Icons.SHIELD_ROUNDED),
        ("special", "Навык", ft.Icons.AUTO_AWESOME_ROUNDED),
        ("dodge", "Уворот", ft.Icons.DOUBLE_ARROW_ROUNDED),
        ("charge", "Фокус", ft.Icons.CENTER_FOCUS_STRONG_ROUNDED),
    ]
    if battle.get('rules_version')==3:
        from combat_rules import allowed,current_actor
        actor=current_actor(battle)
        choices += [(a,label,icon) for a,label,icon in [
            ('quick','Быстрый',ft.Icons.SPEED_ROUNDED),('pierce','Пробитие',ft.Icons.GPS_FIXED_ROUNDED),
            ('burst','Серия',ft.Icons.GRAIN_ROUNDED),('emp','EMP',ft.Icons.WIFI_OFF_ROUNDED),('ultimate','Супер',ft.Icons.AUTO_AWESOME_ROUNDED)] if a in allowed(actor)]
    for action,label,icon in choices:

        async def act(_, move=action, battle_id=identity, expected=turn):
            await animate_turn(session, move, battle_id, expected)

        unavailable = not active or busy
        if battle.get('rules_version')==3:
            from combat_rules import action_error,current_actor
            unavailable |= bool(action_error(current_actor(battle),action))
        if action == "special":
            unavailable |= battle["cooldown"] > 0 or battle.get("focus", 2) < 2
        if action == "dodge":
            unavailable |= (
                battle.get("dodge_cooldown", 0) > 0 or battle.get("focus", 2) < 1
            )
        style = button_style(state.accent, secondary=action in {"guard", "charge"})
        style.text_style = ft.TextStyle(
            size=12, weight=ft.FontWeight.W_600, font_family="Roboto"
        )
        style.icon_size = 18
        style.padding = ft.Padding.symmetric(horizontal=8, vertical=11)
        narrow = (getattr(session.page, "width", None) or 420) < 360
        buttons.append(
            ft.Container(
                ft.Button(
                    label,
                    icon=icon,
                    key=f"arena-{action}",
                    on_click=act,
                    disabled=unavailable,
                    tooltip=SPECIALS[battle["robot_id"]][1]
                    if action == "special"
                    else hints_tooltip(action),
                    style=style,
                    width=float("inf"),
                ),
                col=6 if wide or narrow else 4,
            )
        )
    intent = enemy_intent(battle)
    text = INTENT_NAMES[intent]
    if busy:
        text = "Роботы выполняют ход…"
    hints = {
        "attack": "Удар восстанавливает 1 фокус",
        "guard": "Щит снизит сильный ответ",
        "special": "Сейчас можно использовать приём",
        "dodge": "Уклонение поможет избежать атаки",
        "charge": "В защитную стойку лучше не бить",
        'quick':'Быстрый удар прервёт подготовку',
        'pierce':'Пробитие разрушит стойку',
        'burst':'Серия осложнит уклонение',
        'emp':'EMP отключит энергетический щит',
        'ultimate':'Суперспособность полностью заряжена',
    }
    controls = [
        ft.Row(
            [
                ft.Icon(ft.Icons.VISIBILITY_ROUNDED, color=state.accent, size=20),
                ft.Text(
                    text, size=12, color=INK, weight=ft.FontWeight.BOLD, expand=True
                ),
                BattleHelp(session=session),
            ],
            spacing=7,
        ),
        ft.Row(
            [
                ft.Text("Фокус", size=10, color=MUTED),
                *(
                    [
                        ft.Text(
                            f"⚡ {battle.get('battery', 12)}/12",
                            size=10,
                            color=state.accent,
                        )
                    ]
                    if battle.get("equipment")
                    else []
                ),
                *[
                    ft.Icon(
                        ft.Icons.CIRCLE,
                        size=12,
                        color=state.accent if i < battle.get("focus", 2) else "#DCE3EF",
                    )
                    for i in range(3)
                ],
                ft.Text(
                    "Перегрев!"
                    if battle.get("heat", 0) >= 2
                    else f"Нагрев {battle.get('heat', 0)}/3",
                    size=10,
                    color="#C66C55" if battle.get("heat", 0) >= 2 else MUTED,
                    expand=True,
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            spacing=5,
        ),
        ft.ResponsiveRow(buttons, spacing=6, run_spacing=7),
        *([ft.Text(f'Суперспособность: {battle.get("super_charge",0)}% · Энергия {battle.get("battery",12)}/{battle.get("max_battery",12)}',color=GOLD,size=11),ft.ProgressBar(value=battle.get('super_charge',0)/100,color=GOLD,bgcolor='#294260',height=7,border_radius=4)] if battle.get('rules_version')==3 else []),
        ft.Text(
            f"{SPECIALS[battle['robot_id']][0]} · "
            + (
                f"готов через {battle['cooldown']} хода"
                if battle["cooldown"]
                else "2 фокуса"
            ),
            size=10,
            color=state.accent,
        ),
        ft.Text(
            hints[suggested_action(battle)]
            if battle["stage"] < 3
            else "Чередуй действия, учитывай стихию и намерение соперника",
            size=10,
            color=MUTED,
        ),
        ft.Text(SPECIALS[battle["robot_id"]][1], size=10, color=MUTED),
    ]
    return card(
        ft.Column(controls, spacing=9), padding=12, bgcolor=tint(state.accent, 0.97)
    )


@ft.component
def ArenaBattles(page, device_id, session=None, on_home=None):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    battle = state.battle
    active = battle.get("result") == "active"
    animating = session.arena_animating and session.arena_visual.get(
        "battle_id"
    ) == battle.get("id")
    width = (getattr(page, "width", None) or 420) - 12
    wide = session.arena_expanded and width >= 650
    if active or animating:

        async def leave(_):
            session.act("battle_leave")

        leave_button = ft.TextButton("Выйти из боя", key="arena-leave", on_click=leave)
        if wide:
            return ft.Row(
                [
                    ft.Container(
                        battle_scene(
                            page, session, battle, width_override=width * 0.62 - 10
                        ),
                        expand=3,
                    ),
                    ft.Container(
                        ft.Column(
                            [action_panel(session, wide=True), leave_button],
                            spacing=4,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        expand=2,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
                expand=True,
            )
        return ft.Column(
            [
                battle_scene(page, session, battle),
                action_panel(session),
                ft.Text(battle["log"][-1], size=10, color=MUTED),
                leave_button,
            ],
            spacing=9,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    controls = [
        heading("Лига роботов", "Расти, выбирай тактику и открывай новые арены"),
        notice(session),
    ]
    if not state.tutorial_seen:

        async def understood(_):
            session.act("tutorial_done")

        controls.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            "Первый бой: три простых шага",
                            size=14,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "1. Прочитай намерение соперника.\n2. Рывок — уворот, энергокольцо — щит.\n3. Копи фокус для своего навыка.",
                            size=12,
                            color=MUTED,
                        ),
                        ft.Text(
                            "Кнопка в углу поля открывает только бой в горизонтальном виде",
                            size=11,
                            color=state.accent,
                        ),
                        ft.TextButton(
                            "Понятно", on_click=understood, key="arena-tutorial-done"
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor=tint(state.accent, 0.94),
            )
        )
    if not state.robot_levels:
        controls.append(
            card(
                ft.Column(
                    [
                        ft.Image("art/egg_starter.webp", width=110, height=120),
                        ft.Text(
                            "Твой первый боец ждёт в яйце",
                            size=18,
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Открой яйцо в мастерской, чтобы начать путешествие по аренам",
                            size=12,
                            color=MUTED,
                        ),
                        *(
                            [
                                ft.Button(
                                    "В мастерскую",
                                    on_click=on_home,
                                    style=button_style(state.accent),
                                )
                            ]
                            if on_home
                            else []
                        ),
                    ],
                    spacing=12,
                )
            )
        )
        return ft.Column(controls, spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    if battle:
        won = battle["result"] == "win"
        controls.append(
            card(
                ft.Row(
                    [
                        badge("arena" if won else "food", 47),
                        ft.Column(
                            [
                                ft.Text(
                                    "Победа! Следующая точка открыта"
                                    if won
                                    else "Новая попытка — новая тактика",
                                    size=16,
                                    color=INK,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"Получено {battle['reward']} монет, 4 корма и опыт"
                                    if won
                                    else "Робот и монеты сохранены. Подкорми бойца и попробуй другой приём.",
                                    size=11,
                                    color=MUTED,
                                ),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    spacing=11,
                ),
                bgcolor="#FFF3D9" if won else tint(state.accent, 0.92),
            )
        )
    controls.extend([arena_options(session), route_map(state), food_bar(session)])
    selected = state.active_robot or next(iter(state.robot_levels))
    choices = []
    for robot in ROBOTS:
        if robot.id not in state.robot_levels:
            continue

        async def select(_, identity=robot.id):
            session.act("select_robot", identity)

        choices.append(
            ft.Container(
                ft.Column(
                    [
                        robot_actor(robot.id, size=72, now=session.clock()),
                        ft.Text(
                            robot.name, size=11, color=INK, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            f"{state.robot_levels[robot.id]} ур. · {ELEMENT_NAMES[ELEMENTS[robot.id]]}",
                            size=9,
                            color=MUTED,
                        ),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=select,
                key=f"arena-robot-{robot.id}",
                padding=9,
                border_radius=16,
                bgcolor=tint(state.accent, 0.8) if robot.id == selected else "white",
            )
        )
    controls.append(ft.Row(choices, spacing=8, scroll=ft.ScrollMode.AUTO))
    preview = new_battle(selected, state.robot_levels[selected], state.arena_stage + (state.tournament.get("wins",0) if state.tournament.get("active") else 0), 0)
    from armory import equip_battle

    equip_battle(state,preview)
    controls.append(battle_scene(page, session, preview, preview=True))
    enemy = enemy_for(preview['stage'])
    enemy.update(health=preview['enemy_max_hp'],attack=preview['enemy_attack'],reward=preview['reward'])
    affinity = element_multiplier(selected, enemy["robot_id"])
    health, attack = robot_stats(selected, state.robot_levels[selected])
    controls.append(
        card(
            ft.Column(
                [
                    ft.Row(
                        [
                            badge("arena", 32),
                            ft.Text(
                                enemy["name"],
                                size=17,
                                color=INK,
                                weight=ft.FontWeight.BOLD,
                                expand=True,
                            ),
                        ]
                    ),
                    ft.Text(
                        f"Твой боец: {health} здоровья · {attack} атаки",
                        size=11,
                        color=MUTED,
                    ),
                    ft.Text(
                        "Стихия даёт преимущество"
                        if affinity > 1
                        else "Соперник сильнее по стихии: пригодятся щит и уклонения"
                        if affinity < 1
                        else "Равные стихии: исход решит тактика",
                        size=11,
                        color=GREEN if affinity >= 1 else "#AD7543",
                    ),
                    ft.Text(
                        f"Награда: {enemy['reward']} монет + 4 корма",
                        size=11,
                        color=GREEN,
                    ),
                ],
                spacing=9,
            )
        )
    )
    controls.append(care_panel(session))

    async def start(_):
        session.act("battle_start", selected)

    controls.append(
        ft.Button(
            "На арену · 20 заряда",
            icon=ft.Icons.SPORTS_MARTIAL_ARTS_ROUNDED,
            key="arena-start",
            on_click=start,
            disabled=state.robot_energy.get(selected, 70) < BATTLE_ENERGY,
            style=button_style(state.accent),
            width=float("inf"),
        )
    )
    controls.append(
        ft.Text(
            "Заряд возвращается со временем. Поражение не отнимает робота или накопленные монеты.",
            size=11,
            color=MUTED,
        )
    )
    return ft.Column(controls, spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)


@ft.component
def ArenaScreen(page, device_id, session=None, on_home=None):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    tab, set_tab = ft.use_state(0)

    async def battles(_):
        set_tab(0)

    async def ranking(_):
        if session.arena_expanded:
            await set_arena_expanded(page, session, False)
        set_tab(1)

    async def online(_):
        set_tab(2)

    async def clans(_):
        set_tab(3)

    body = (
        ArenaBattles(page=page, device_id=device_id, session=session, on_home=on_home)
        if tab == 0
        else LeaderboardScreen(page=page, device_id=device_id, session=session)
        if tab == 1
        else OnlineScreen(page=page, session=session, clans=tab == 3)
    )
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Button(
                        "Арены",
                        on_click=battles,
                        icon=ft.Icons.SPORTS_MARTIAL_ARTS_ROUNDED,
                        style=button_style(state.accent, secondary=tab != 0),
                        expand=True,
                    ),
                    ft.Button(
                        "Рейтинг",
                        on_click=ranking,
                        style=button_style(state.accent, secondary=tab != 1),
                        expand=True,
                    ),
                    ft.Button(
                        "PvP",
                        on_click=online,
                        key="pvp-tab",
                        style=button_style(state.accent, secondary=tab != 2),
                        expand=True,
                    ),
                    ft.Button(
                        "Кланы",
                        on_click=clans,
                        key="clans-tab",
                        style=button_style(state.accent, secondary=tab != 3),
                        expand=True,
                    ),
                ],
                spacing=6,
            ),
            ft.Container(body, expand=True),
        ],
        spacing=8,
        expand=True,
    )


def arena_screen(page, device_id, session=None, on_home=None):
    return ArenaScreen(page=page, device_id=device_id, session=session, on_home=on_home)
