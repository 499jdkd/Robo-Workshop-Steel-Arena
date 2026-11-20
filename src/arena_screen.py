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


@ft.component
def BattleHelp(session):
    from combat_info import ACTION_TITLES

    opened, set_opened = ft.use_state(False)
    step, set_step = ft.use_state(0)
    answer, set_answer = ft.use_state("")
    lessons = [
        ("Энергия закончилась. Как продолжить бой?", ["charge", "special"], "charge",
         "Фокус бесплатный: +6 энергии при восстановлении 3 и +2 фокуса. Щит тоже бесплатный: +3 энергии и +1 фокус."),
        ("Соперник готовит сильный удар. Как прервать подготовку?", ["quick", "attack"], "quick",
         "Быстрый удар прерывает подготовку. Обычный удар даёт больше урона, но не прерывает её."),
        ("Соперник включил щит. Чем отключить его?", ["emp", "attack"], "emp",
         "EMP — электромагнитный импульс. Он снимает щит и отключает его на 2 хода; изоляция сокращает эффект до 1 хода."),
        ("Суперзаряд 100%, но энергии 1/12. Что делать?", ["ultimate", "guard"], "guard",
         "Супер требует ещё 4 энергии. Щит восстановит 3: на следующем ходу будет 4/12. Фокус восстанавливает ещё больше, но делает тебя уязвимее."),
    ]
    question, choices, correct, explanation = lessons[step]

    async def show(_):
        set_step(0)
        set_answer("")
        set_opened(True)

    async def close(_):
        set_opened(False)

    async def next_step(_):
        if step + 1 == len(lessons):
            session.act("tutorial_done")
            set_opened(False)
        else:
            set_step(step + 1)
            set_answer("")

    def choose(action):
        async def selected(_):
            set_answer(action)
        return selected

    ft.use_dialog(
        ft.AlertDialog(
            title=ft.Text("Как сражаться", size=20),
            content=ft.Column([
                ft.Text(f"Тренировка {step + 1} / {len(lessons)} · без расхода ресурсов", size=12, color=MUTED),
                ft.ProgressBar(value=(step + 1) / len(lessons), color=GOLD),
                ft.Text(question, size=17, color=INK, weight=ft.FontWeight.BOLD),
                *[ft.Button(ACTION_TITLES[action], on_click=choose(action), height=50,
                            style=button_style(session.state.accent), width=float("inf")) for action in choices],
                *([ft.Text("Верно! " + explanation if answer == correct else "Попробуй другой приём. " + explanation,
                           size=13, color=GREEN if answer == correct else GOLD)] if answer else []),
                ft.Text("Энергия оплачивает приёмы. Фокус нужен навыку. Нагрев ослабляет повторные удары. Суперзаряд накапливается от действий и попаданий.", size=12, color=MUTED),
            ], spacing=12, tight=True, width=310, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Позже", on_click=close),
                     ft.Button("В бой" if step == 3 else "Далее", on_click=next_step, disabled=answer != correct, height=48)],
            on_dismiss=close,
        ) if opened else None
    )
    return ft.IconButton(ft.Icons.HELP_OUTLINE_ROUNDED, tooltip="Пройти короткое обучение",
                         on_click=show, key="arena-help", width=48, height=48)


def battle_settings(session):
    async def speed(_):
        speeds = (1.0, 1.5, 2.0)
        session.presentation(speed=speeds[(speeds.index(session.battle_speed) + 1) % len(speeds)])

    async def effects(event):
        session.presentation(reduced=event.control.value)

    return ft.Row([
        ft.TextButton(f"Скорость ×{session.battle_speed:g}", on_click=speed,
                      icon=ft.Icons.SPEED_ROUNDED, height=48, key="battle-speed",
                      disabled=session.arena_animating),
        ft.Switch(label="Меньше эффектов", value=session.reduced_effects,
                  on_change=effects, label_text_style=ft.TextStyle(size=11), key="battle-effects"),
    ], spacing=5, wrap=True)


def action_panel(session, *, wide=False):
    from copy import deepcopy
    from combat_rules import allowed, current_actor, fighter
    from combat_info import action_control
    from battle_ui import battle_action_error
    from robot_abilities import ABILITIES
    from robot_designs import DESIGNS

    battle, state = session.state.battle, session.state
    identity, turn = battle["id"], battle["turn"]
    active, busy = battle["result"] == "active", session.arena_animating
    modern = battle.get("rules_version") == 3
    if modern:
        actor = current_actor(battle)
        target = deepcopy(battle["combatants"]["b"])
        intent = enemy_intent(battle)
        target["guard"] = intent == "guard" and not target["emp"]
        target["preparing"] = intent == "windup"
    else:
        from armory import equipped_weapon
        gear, _ = equipped_weapon(battle)
        actor = fighter(battle["robot_id"], gear.id if gear else DESIGNS[battle["robot_id"]]["weapon"])
        actor.update(energy=battle.get("battery", 12), focus=battle.get("focus", 2),
                     heat=battle.get("heat", 0), cooldown=battle.get("cooldown", 0),
                     dodge_cooldown=battle.get("dodge_cooldown", 0))
        target = None
    choices = ["attack", "guard", "special", "dodge", "charge"]
    if modern:
        choices += [a for a in ("quick", "pierce", "burst", "emp", "ultimate") if a in allowed(actor)]
    if actor["energy"] < 2 or actor.get("stun"):
        choices = ["charge", "guard"] + [a for a in choices if a not in {"charge", "guard"}]
    blocked = "Роботы выполняют ход…" if busy else "Бой завершён" if not active else ""
    buttons = []
    for action in choices:
        async def act(_, move=action, battle_id=identity, expected=turn):
            await animate_turn(session, move, battle_id, expected)
        control = action_control(actor, action, act, state.accent, target=target,
                                 blocked=blocked or battle_action_error(battle, action))
        buttons.append(control)

    def meter(label, value, maximum, color, hint):
        return ft.Container(ft.Column([
            ft.Text(f"{label} {value}/{maximum}", size=12, color=color, weight=ft.FontWeight.BOLD),
            ft.ProgressBar(value=value / max(1, maximum), color=color, bgcolor="#253A56", height=5, border_radius=4),
            ft.Text(hint, size=10, color=MUTED),
        ], spacing=4), col=6)

    ability = ABILITIES[battle["robot_id"]]
    controls = [
        ft.Row([
            ft.Icon(ft.Icons.VISIBILITY_ROUNDED, color=state.accent, size=22),
            ft.Text(blocked or INTENT_NAMES[enemy_intent(battle)], size=13, color=INK,
                    weight=ft.FontWeight.BOLD, expand=True),
            BattleHelp(session=session),
        ], spacing=7),
        ft.ResponsiveRow([
            meter("Энергия", actor["energy"], actor["max_energy"], "#74DFFF", "Расход на приёмы"),
            meter("Фокус", actor["focus"], 3, "#C3A7FF", "Навык требует 2"),
            meter("Нагрев", actor["heat"], 3, "#FFAF78", "Щит и фокус охлаждают"),
            meter("Супер", actor["super_charge"], 100, GOLD, "Нужно 100% и 4 энергии"),
        ], spacing=9, run_spacing=9),
    ]
    if modern and actor["energy"] < 2 and active and not busy:
        controls.append(ft.Text(f"Мало энергии. Фокус: +{min(actor['max_energy']-actor['energy'], actor['regen']+3)} энергии. Щит: +{min(actor['max_energy']-actor['energy'], actor['regen'])} энергии. Оба действия бесплатны.", color=GREEN, size=12))
    if actor.get("stun"):
        controls.append(ft.Text("Робот оглушён: выбери бесплатный щит или фокус, чтобы пропустить этот ход.", color=GOLD, size=12))
    if actor["heat"] >= 2:
        controls.append(ft.Text("Нагрев ослабит следующий повторный удар. Щит или фокус полностью охладят корпус.", color="#FFB378", size=12))
    controls += [
        ft.ResponsiveRow(buttons, spacing=7, run_spacing=9),
        ft.Text("Супер · " + ability.title, size=13, color=GOLD, weight=ft.FontWeight.BOLD),
        ft.Text(ability.effect, size=12, color=MUTED),
        ft.Text("Удерживай кнопку для подробностей: эффект, требования, перезарядка и контрприём. Урон примерный, без случайного критического попадания.", size=11, color=MUTED),
        battle_settings(session),
    ]
    return card(ft.Column(controls, spacing=10), padding=12, bgcolor=tint(state.accent, 0.97))


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
    preview = new_battle(
        selected,
        state.robot_levels[selected],
        state.arena_stage
        + (state.tournament.get("wins", 0) if state.tournament.get("active") else 0),
        0,
    )
    from armory import equip_battle

    equip_battle(state, preview)
    controls.append(battle_scene(page, session, preview, preview=True))
    enemy = enemy_for(preview["stage"])
    enemy.update(
        health=preview["enemy_max_hp"],
        attack=preview["enemy_attack"],
        reward=preview["reward"],
    )
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
def RankingScreen(page, session):
    from game_ui import tabs

    selected, set_selected = ft.use_state(0)
    return ft.Column(
        [
            tabs(["Рейтинговые бои", "Мастерские"], selected, set_selected),
            OnlineScreen(page=page, session=session, ranking=True)
            if selected == 0
            else LeaderboardScreen(
                page=page, device_id=session.device_id, session=session
            ),
        ],
        expand=True,
        spacing=9,
    )


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
        else RankingScreen(page=page, session=session)
        if tab == 1
        else OnlineScreen(page=page, session=session, clans=tab == 3)
    )

    def arena_tab(label, index, handler, key):
        style = button_style(state.accent, secondary=tab != index)
        style.padding = ft.Padding.symmetric(horizontal=6, vertical=10)
        return ft.Button(
            ft.Text(label, size=12, weight=ft.FontWeight.BOLD, no_wrap=True),
            on_click=handler,
            key=key,
            height=48,
            style=style,
            expand=True,
        )

    return ft.Column(
        [
            ft.Row(
                [
                    arena_tab("Бои", 0, battles, "arena-tab-battles"),
                    arena_tab("Рейтинг", 1, ranking, "arena-tab-ranking"),
                    arena_tab("PvP", 2, online, "pvp-tab"),
                    arena_tab("Кланы", 3, clans, "clans-tab"),
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
