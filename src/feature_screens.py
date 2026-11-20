"""Factory, season and earned-currency shop, integrated with the main router."""

import flet as ft
import asyncio

from armory import BY_ID, WEAPONS
from collection_progress import (
    CHESTS,
    ODDS,
    RARITY_ORDER,
    ensure,
    refresh_season,
    reward_title,
)
from equipment_catalog import MODULES
from game_countdown import GameCountdown
from game_ui import game_button, resource_hud, section_title, tabs
from progression_ui import stored_eggs_panel
from rewarded_ads import RewardPanel
from robot_catalog import RARITIES, ROBOT_BY_ID, ROBOTS
from season_catalog import LEVEL_XP, LEVELS, reward_at, season_at
from ui_shared import GOLD, GREEN, INK, MUTED, card, notice, tint, use_game


@ft.control("GameFactory")
class GameFactory(ft.Container):
    receipt: str = ""
    opened: bool = False
    container_type: str = "normal"


def navigate(session, destination):
    def go(_):
        session.route = destination
        session.notify()

    return go


def reward_icon(reward):
    kind = reward["kind"]
    identity = reward.get("id", "")
    if kind == "chests":
        return f"art/containers/{identity if identity in CHESTS else 'normal'}.svg"
    if kind in {"fragments", "robot"} and identity in ROBOT_BY_ID:
        return ROBOT_BY_ID[identity].image
    if kind == "blueprints" and identity in BY_ID:
        return f"art/weapons/{identity}.svg"
    if kind == "module":
        return f"art/modules/{identity}.svg"
    return {
        "gold": "art/icons/credits.svg",
        "food": "art/icons/food.svg",
        "crystals": "art/icons/crystal.svg",
        "chests": "art/icons/container.svg",
        "cores": "art/modules/reactor.svg",
        "parts": "art/icons/parts.svg",
        "rare_parts": "art/icons/parts.svg",
        "skin": "art/icons/profile.svg",
        "emblem": "art/icons/arena.svg",
        "animation": "art/icons/profile.svg",
    }.get(kind, "art/icons/parts.svg")


def reward_card(reward, *, status="", premium=False, expand=True):
    color = RARITIES.get(reward.get("rarity", "common"), RARITIES["common"])[1]
    return ft.Container(
        ft.Row(
            [
                ft.Image(
                    reward_icon(reward), width=56, height=64, fit=ft.BoxFit.CONTAIN
                ),
                ft.Column(
                    [
                        ft.Text(
                            reward_title(reward),
                            color=INK,
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            max_lines=3,
                        ),
                        ft.Text(
                            status,
                            color=GREEN
                            if status == "Получено"
                            else GOLD
                            if status == "Доступно"
                            else MUTED,
                            size=11,
                        ),
                    ],
                    expand=True,
                    spacing=3,
                ),
            ],
            spacing=6,
        ),
        padding=7,
        border_radius=10,
        border=ft.Border.all(1, color),
        gradient=ft.LinearGradient(colors=[tint(color, 0.2), "#162844"]),
        expand=expand,
    )


@ft.component
def FeatureScreen(page, session):
    use_game(session)
    screen = session.route
    titles = {"season": "Стальной сезон", "factory": "Робофабрика", "store": "Магазин"}
    header = ft.Row(
        [
            ft.IconButton(
                ft.Icons.ARROW_BACK_ROUNDED,
                on_click=navigate(session, ""),
                icon_color="#8CE2FF",
                key="feature-back",
            ),
            ft.Text(
                titles.get(screen, "Мастерская"),
                color=INK,
                size=22,
                weight=ft.FontWeight.BOLD,
                expand=True,
            ),
        ],
        spacing=6,
    )
    body = (
        SeasonScreen(page=page, session=session)
        if screen == "season"
        else FactoryScreen(page=page, session=session)
        if screen == "factory"
        else StoreScreen(page=page, session=session)
    )
    return ft.Column([header, body], expand=True, spacing=8)


@ft.component
def SeasonScreen(page, session):
    from billing import billing_for, sandbox_available

    billing = billing_for(session)
    state = use_game(session)
    data = ensure(state)
    now = session.clock()
    season = refresh_season(state, now)
    config = season_at(now)
    level = min(LEVELS, season["xp"] // LEVEL_XP)
    available = sum(n not in season["free"] for n in range(1, level + 1))

    def command(name, *args):
        def run(_):
            session.act(name, *args)

        return run

    rows = [
        resource_hud(state),
        card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Image("art/icons/arena.svg", width=57, height=57),
                            ft.Column(
                                [
                                    ft.Text(
                                        "STEEL SEASON",
                                        color=GOLD,
                                        size=23,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(config["name"], color=INK, size=12),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Text(
                        "Сражайся, изобретай и развивай команду. Награды доступны за игру.",
                        color=MUTED,
                        size=11,
                    ),
                    ft.Text(
                        f"Уровень сезона {level} / {LEVELS} · Опыт {season['xp']} / {LEVEL_XP * LEVELS}",
                        color=INK,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.ProgressBar(
                        value=1
                        if level == LEVELS
                        else (season["xp"] % LEVEL_XP) / LEVEL_XP,
                        color="#D78AFF",
                        bgcolor="#293657",
                        height=12,
                        border_radius=6,
                    ),
                    ft.Text(
                        f"До завершения: {max(0, int((config['end'] - now) // 86400))} дн. {max(0, int((config['end'] - now) // 3600) % 24)} ч.",
                        color="#93DBFF",
                        size=11,
                    ),
                    game_button(
                        f"Забрать всё · {available}",
                        command("season_claim_all"),
                        key="season-claim-all",
                        disabled=not available,
                    ),
                ],
                spacing=10,
            ),
            gradient=ft.LinearGradient(colors=["#294B84", "#2A2257"]),
        ),
        card(
            ft.Text(
                "Бесплатная линия приносит ресурсы и фрагменты. Премиум пока закрыт: подключение платежей не завершено. Нормализованный PvP не учитывает сезонные бонусы.",
                color=MUTED,
                size=11,
            )
        ),
        ft.Row(
            [
                ft.Text(
                    "БЕСПЛАТНО",
                    color="#81DAFF",
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text("Ур.", color=GOLD, size=11),
                ft.Text(
                    "ПРЕМИУМ 🔒",
                    color=GOLD,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=6,
        ),
    ]
    if sandbox_available():
        rows.insert(
            2,
            card(
                ft.Column(
                    [
                        ft.Text(
                            "ТЕСТ ПРЕМИУМА · без оплаты",
                            color=GOLD,
                            weight=ft.FontWeight.BOLD,
                            size=13,
                        ),
                        ft.Text(
                            "Предпросмотр временный: премиальные награды не добавляются в игровой инвентарь и исчезнут после выхода.",
                            color=MUTED,
                            size=11,
                        ),
                        game_button(
                            "Закрыть тест"
                            if billing.preview
                            else "Открыть тестовую линию",
                            lambda _: billing.toggle_preview(),
                            kind="purple",
                            key="billing-sandbox",
                        ),
                    ],
                    spacing=8,
                )
            ),
        )
    if billing.rewards:
        rows.insert(
            3,
            card(
                ft.Text(
                    "Тестовая выдача: "
                    + ", ".join(reward_title(r) for r in billing.rewards[-3:]),
                    color=GOLD,
                    size=11,
                )
            ),
        )
    for n in range(1, LEVELS + 1):
        claimed = n in season["free"]
        ready = n <= level and not claimed
        free = reward_card(
            reward_at(n),
            status="Получено"
            if claimed
            else "Доступно"
            if ready
            else f"{n * LEVEL_XP} XP",
        )
        free.on_click = command("season_claim", n, "free") if ready else None
        paid = reward_card(
            reward_at(n, True),
            status=(
                "Тест: получено"
                if n in billing.claims
                else "Тест: доступно"
                if n <= level
                else "Тест: закрыто"
            )
            if billing.preview
            else "Премиум закрыт",
            premium=True,
        )
        if billing.preview and n <= level and n not in billing.claims:
            paid.on_click = lambda _, number=n: billing.claim_preview(number)
        rows.append(
            ft.Row(
                [
                    free,
                    ft.Container(
                        ft.Text(str(n), color=GOLD, size=14, weight=ft.FontWeight.BOLD),
                        width=22,
                        alignment=ft.Alignment.CENTER,
                    ),
                    paid,
                ],
                spacing=5,
            )
        )
    from progression_ui import daily_panel
    from armory_ui import weekly_panel

    rows.extend(
        [
            section_title("Задания сезона"),
            daily_panel(session),
            weekly_panel(session),
            notice(session),
        ]
    )
    return ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)


@ft.component
def FactoryScreen(page, session):
    state = use_game(session)
    data = ensure(state)
    kind = session.factory_kind
    reward_view = session.factory_rewards_visible

    def set_kind(value):
        session.factory_kind = value
        session.notify()

    def set_reward_view(value):
        session.factory_rewards_visible = value
        session.notify()
    last_receipt = ft.use_ref(data["factory_receipt"])

    def received():
        if last_receipt.current == data["factory_receipt"]:
            return
        last_receipt.current = data["factory_receipt"]
        async def reveal():
            await asyncio.sleep(2)
            if session.ui_alive:
                set_reward_view(True)
        task = asyncio.create_task(reveal())
        return task.cancel

    ft.use_effect(received, [data["factory_receipt"]])

    if reward_view and data["factory_rewards"]:
        async def back(_):
            set_reward_view(False)
        return ft.Column([
            resource_hud(state),
            section_title("Твои награды", "Все предметы уже сохранены"),
            ft.ResponsiveRow([
                ft.Container(card(ft.Column([
                    ft.Image(reward_icon(reward), width=120, height=128, fit=ft.BoxFit.CONTAIN),
                    ft.Text(reward_title(reward), color=INK, size=15, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("Получено", color=GREEN, size=12),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=9)), col={"xs": 6, "md": 4})
                for reward in data["factory_rewards"]
            ], spacing=9, run_spacing=9),
            game_button("К контейнерам", back, kind="blue", key="factory-rewards-back"),
        ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)

    def command(name, *args):
        def run(_):
            session.act(name, *args)

        return run

    chest = CHESTS[kind]
    count = data["chests"].get(kind, 0)
    rows = [
        resource_hud(state),
        card(
            ft.Column(
                [
                    section_title(chest[0], f"В хранилище: {count}"),
                    GameFactory(
                        container_type=kind,
                        receipt=data["factory_receipt"],
                        opened=bool(data["factory_receipt"]),
                        height=230,
                        key="factory-opening",
                    ),
                    ft.Row(
                        [
                            game_button(
                                "Открыть",
                                command("factory_open", kind, 1),
                                key="factory-open",
                                disabled=count < 1,
                                expand=True,
                            ),
                            game_button(
                                "Открыть ×5",
                                command("factory_open", kind, 5),
                                kind="blue",
                                key="factory-open-five",
                                disabled=count < 5,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    game_button(
                        f"Купить · {chest[1]} золота",
                        command("factory_buy", kind, 1),
                        kind="green",
                        disabled=state.coin < chest[1],
                    ),
                ],
                spacing=10,
            ),
            padding=12,
        ),
        tabs(
            [
                v[0].replace("Контейнер ", "").replace(" контейнер", "")
                for v in CHESTS.values()
            ],
            list(CHESTS).index(kind),
            lambda i: set_kind(list(CHESTS)[i]),
        ),
        game_button(
            "Бесплатный контейнер дня",
            command("factory_daily"),
            kind="purple",
            key="factory-daily",
            disabled=int(session.clock() // 86400) <= data["factory_day"],
        ),
        notice(session),
    ]
    if data["factory_rewards"]:
        async def show_rewards(_):
            set_reward_view(True)
        rows.append(game_button("Посмотреть награды", show_rewards,
                                kind="gold", key="factory-show-rewards"))
        rows.append(
            section_title("Полученные предметы", "Награды уже записаны в сохранение")
        )
        for reward in data["factory_rewards"]:
            rows.append(reward_card(reward, expand=False))
    weights = ODDS.get(kind)
    if weights:
        rows.append(
            card(
                ft.Column(
                    [
                        ft.Text(
                            "Вероятности редкости",
                            color=INK,
                            weight=ft.FontWeight.BOLD,
                            size=13,
                        ),
                        ft.Text(
                            " · ".join(
                                f"{RARITIES[r][0]} {w / 100:g}%"
                                for r, w in zip(RARITY_ORDER, weights)
                            ),
                            color=MUTED,
                            size=11,
                        ),
                        ft.Text(
                            "Гарантированный путь: фрагменты за победы, задания и прямую покупку за заработанное золото. Контейнеры не продаются за реальные деньги.",
                            color=MUTED,
                            size=11,
                        ),
                        ft.Text(
                            "Роботы внутри одной редкости равновероятны. Капсула: 15% — готовый робот, 85% — 8 фрагментов. Дубликат готового робота превращается во фрагменты по стоимости его открытия."
                            if kind == "capsule"
                            else "В каждом таком контейнере — 3–6 фрагментов. Роботы внутри одной редкости равновероятны.",
                            color=MUTED,
                            size=11,
                        ),
                    ],
                    spacing=7,
                )
            )
        )
    else:
        rows.append(
            card(
                ft.Text(
                    "Оружейный контейнер: 3–6 чертежей одного из 20 видов оружия, каждый с вероятностью 5%, и 40 золота. Ящик деталей: 6–12 деталей равновероятно и 1 ядро.",
                    color=MUTED,
                    size=11,
                )
            )
        )
    rows.extend([stored_eggs_panel(session), RewardPanel(page=page, session=session)])
    return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


@ft.component
def StoreScreen(page, session):
    state = use_game(session)
    data = ensure(state)
    tab, set_tab = ft.use_state(0)

    def command(name, *args):
        def run(_):
            session.act(name, *args)

        return run

    rows = [
        resource_hud(state),
        tabs(
            ["Роботы", "Оружие", "Модули", "Контейнеры", "Внешний вид", "Предложения"],
            tab,
            set_tab,
        ),
        notice(session),
    ]
    if tab in {0, 5}:
        robots = (
            list(ROBOTS)
            if tab == 0
            else [
                ROBOTS[int(session.clock() // 86400) % len(ROBOTS)],
                ROBOTS[(int(session.clock() // 86400) + 7) % len(ROBOTS)],
            ]
        )
        if tab == 5:
            rows.append(
                card(
                    ft.Text(
                        "Предложения дня обновляются в 00:00 UTC. Стоимость видна заранее, случайной покупки нет.",
                        color=MUTED,
                        size=11,
                    )
                )
            )
        for robot in robots:
            price = 30 + DESIGN_UNLOCK(robot.id) * 5

            def details(_, identity=robot.id):
                session.route = ""
                session.robot_detail = identity
                session.robot_detail_return = "store"
                session.notify()

            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(robot.image, width=96, height=112),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                robot.name,
                                                color=INK,
                                                size=15,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                RARITIES[robot.rarity][0]
                                                + f" · Фрагменты {data['fragments'].get(robot.id, 0)}",
                                                color=RARITIES[robot.rarity][1],
                                                size=11,
                                            ),
                                            ft.Text(robot.story, color=MUTED, size=10),
                                        ],
                                        expand=True,
                                        spacing=4,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                [
                                    game_button(
                                        f"1 фрагмент · {price}",
                                        command("fragment_buy", robot.id),
                                        kind="green",
                                        disabled=state.coin < price,
                                        expand=True,
                                    ),
                                    game_button(
                                        "Профиль",
                                        details,
                                        kind="blue",
                                        expand=True,
                                        key=f"store-robot-{robot.id}",
                                    ),
                                ],
                                spacing=7,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=12,
                )
            )
    elif tab == 1:
        from armory_ui import armory_panel

        rows.extend(armory_panel(session))
    elif tab == 2:
        from equipment_catalog import module_cost

        rows.append(
            card(
                ft.Column(
                    [
                        section_title("Материалы"),
                        game_button(
                            "12 деталей · 180 золота",
                            command("materials_buy", "parts"),
                            kind="green",
                            disabled=state.coin < 180,
                        ),
                        game_button(
                            "Энергетическое ядро · 400 золота",
                            command("materials_buy", "cores"),
                            kind="blue",
                            disabled=state.coin < 400,
                        ),
                        game_button(
                            "2 редкие детали · 320 золота",
                            command("materials_buy", "rare_parts"),
                            kind="purple",
                            disabled=state.coin < 320,
                        ),
                    ],
                    spacing=8,
                )
            )
        )
        for module in MODULES:
            level = data["modules"].get(module.id, 0)
            price = module_cost(module, level)
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        f"art/modules/{module.id}.svg",
                                        width=80,
                                        height=80,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                module.title,
                                                color=INK,
                                                size=14,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                module.description, color=MUTED, size=11
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                ],
                                spacing=9,
                            ),
                            game_button(
                                f"{'Улучшить' if level else 'Купить'} · {price}",
                                command(
                                    "module_upgrade" if level else "module_buy",
                                    module.id,
                                ),
                                kind="green",
                                disabled=level >= 10 or state.coin < price,
                            ),
                        ],
                        spacing=9,
                    )
                )
            )
    elif tab == 3:
        for identity, (title, price) in CHESTS.items():
            rows.append(
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Image(
                                        "art/icons/container.svg", width=56, height=56
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                title,
                                                color=INK,
                                                size=14,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                "В инвентаре: "
                                                + str(data["chests"].get(identity, 0)),
                                                color=MUTED,
                                                size=11,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                [
                                    game_button(
                                        f"Купить · {price}",
                                        command("factory_buy", identity),
                                        disabled=state.coin < price,
                                        expand=True,
                                    ),
                                    game_button(
                                        "Робофабрика",
                                        navigate(session, "factory"),
                                        kind="blue",
                                        expand=True,
                                    ),
                                ],
                                spacing=8,
                            ),
                        ],
                        spacing=8,
                    )
                )
            )
    else:
        rows.append(
            card(
                ft.Column(
                    [
                        section_title("Облики и эмоции"),
                        ft.Text(
                            "Доступны в бесплатной линии сезона и за достижения. Перейди в профиль робота → «Внешний вид», чтобы применить открытую окраску.",
                            color=MUTED,
                            size=12,
                        ),
                        game_button("Открыть сезон", navigate(session, "season")),
                    ],
                    spacing=10,
                )
            )
        )
        from cosmetic_catalog import SKINS, skin_price

        for skin, title in SKINS.items():
            owned = skin in data["skins"]
            price = skin_price(skin)
            rows.append(
                card(
                    ft.Row(
                        [
                            ft.Image(f"art/skins/{skin}.svg", width=72, height=88),
                            ft.Column(
                                [
                                    ft.Text(
                                        title,
                                        color=INK,
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        "Косметика для любого робота · без изменения характеристик",
                                        color=MUTED,
                                        size=10,
                                    ),
                                    game_button(
                                        "Открыто"
                                        if owned
                                        else f"Купить · {price} золота",
                                        command("skin_buy", skin),
                                        kind="purple",
                                        disabled=owned or state.coin < price,
                                    ),
                                ],
                                expand=True,
                                spacing=7,
                            ),
                        ],
                        spacing=10,
                    )
                )
            )
    return ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


def DESIGN_UNLOCK(identity):
    from robot_designs import DESIGNS

    return DESIGNS[identity]["unlock"]
