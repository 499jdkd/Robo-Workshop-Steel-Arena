import flet as ft

from armory_ui import armory_panel

from game_session import preview_session
from gameplay import compact
from progression_ui import stored_eggs_panel, supplies_panel
from rewarded_ads import RewardPanel
from robot_care_ui import food_bar
from robot_catalog import ROBOT_BY_ID, ROBOTS
from robot_ui import incubator_card, robot_card, team_summary
from ui_shared import INK, MUTED, button_style, card, heading, notice, use_game, wallet


@ft.component
def ShopCard(
    image_src,
    label,
    price,
    on_buy,
    can_afford,
    lvl,
    description="",
    accent="#4E7BF2",
    extra="",
):
    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Image(image_src, width=54, height=54, cache_width=108),
                        ft.Container(
                            content=ft.Text(
                                f"{lvl} ур.",
                                size=10,
                                color=accent,
                                weight=ft.FontWeight.BOLD,
                            ),
                            bgcolor="#EEF2FC",
                            padding=7,
                            border_radius=9,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    ft.Text(
                        label,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color=INK,
                        max_lines=2,
                    ),
                    height=40,
                ),
                ft.Container(
                    ft.Text(description, size=11, color=MUTED, max_lines=3), height=44
                ),
                ft.Text(
                    f"{compact(price)} золота",
                    size=15,
                    color=INK,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Button(
                    "Улучшить" if not extra else extra,
                    on_click=on_buy,
                    disabled=not can_afford,
                    style=button_style(accent, secondary=not can_afford),
                    width=float("inf"),
                ),
            ],
            spacing=10,
        ),
        padding=14,
        col=6,
    )


@ft.component
def ShopScreen(page: ft.Page, device_id: str, session=None, on_home=None):
    session = session or preview_session(page, device_id)
    state = use_game(session)
    tab, set_tab = ft.use_state(0)
    now = session.clock()
    from collection_ui import CollectionPanel,RobotDetail
    if session.robot_detail:
        return RobotDetail(page=page,session=session,identity=session.robot_detail,on_home=on_home)

    async def robots_tab(_):
        set_tab(0)

    async def upgrades_tab(_):
        set_tab(1)

    async def boxes_tab(_):
        set_tab(2)

    async def weapons_tab(_):
        set_tab(3)

    def tab_style(index):
        style = button_style(state.accent, secondary=tab != index)
        style.padding = ft.Padding.symmetric(horizontal=5, vertical=12)
        style.text_style = ft.TextStyle(
            size=12, weight=ft.FontWeight.W_600, font_family="Roboto"
        )
        return style

    controls = [
        heading(
            "Твоя команда", "Открывай друзей. Развивай их способности", wallet(state)
        ),
        food_bar(session),
        ft.Row(
            [
                ft.Button(
                    "Арсенал",
                    on_click=weapons_tab,
                    key="armory-tab",
                    style=tab_style(3),
                    expand=True,
                ),
                ft.Button(
                    "Роботы",
                    on_click=robots_tab,
                    style=tab_style(0),
                    expand=True,
                ),
                ft.Button(
                    "Улучшения",
                    on_click=upgrades_tab,
                    style=tab_style(1),
                    expand=True,
                ),
                ft.Button(
                    "Боксы",
                    on_click=boxes_tab,
                    style=tab_style(2),
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        notice(session),
    ]
    if not session.trusted:
        controls.append(
            card(
                ft.Text(
                    "Прежний баланс ещё загружается. Пока доступны монеты, заработанные здесь",
                    size=12,
                    color=MUTED,
                ),
                bgcolor="#EDF2FC",
            )
        )
    if tab == 0:
        return ft.Column([controls[2],CollectionPanel(page=page,session=session,on_home=on_home)],spacing=8,expand=True)
    elif tab == 3:
        controls.extend(armory_panel(session))
    elif tab == 1:
        upgrades = (
            (
                "click",
                ROBOT_BY_ID["spark"].image,
                "Сила касания",
                "+1 монета за нажатие. Складывается со способностями команды.",
                state.double_click_price,
                state.base_click_power - 1,
            ),
            (
                "auto",
                ROBOT_BY_ID["volt"].image,
                "Автосборщик",
                "+1 монета в секунду на любом экране игры. Работает вместе с роботами.",
                state.auto_click_price,
                state.base_auto_click_power,
            ),
            (
                "offline",
                ROBOT_BY_ID["flora"].image,
                "Доход в отдыхе",
                "+1 монета в минуту вне игры. Награда за отдых до 24 часов.",
                state.offline_income_price,
                state.offline_income_power,
            ),
            (
                "boost",
                ROBOT_BY_ID["nova"].image,
                "Суперрежим",
                "На 20 секунд усиливает касания и команду. Каждый запуск мощнее.",
                state.boost_price,
                state.boost_level,
            ),
        )
        cards = []
        for kind, image, label, description, price, level in upgrades:

            async def purchase(_, upgrade=kind):
                session.act("buy", upgrade)

            active = kind == "boost" and state.boost_end_at > now
            cards.append(
                ShopCard(
                    image,
                    label,
                    price,
                    purchase,
                    session.trusted and state.coin >= price and not active,
                    level,
                    description,
                    state.accent,
                    f"Ещё {int(state.boost_end_at - now + 0.99)} с" if active else "",
                )
            )
        controls.extend(
            [
                ft.ResponsiveRow(cards, columns=12, spacing=10, run_spacing=10),
                card(
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                                color=state.accent,
                                size=23,
                            ),
                            ft.Text(
                                "Опыт остаётся с тобой после покупок. Роботы усиливают мастерскую вместе с этими улучшениями.",
                                size=12,
                                color=MUTED,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                    bgcolor="#EDF2FC",
                ),
            ]
        )
    else:
        controls.extend(
            [
                stored_eggs_panel(session),
                supplies_panel(session),
                RewardPanel(page=page, session=session),
            ]
        )
    return ft.Column(controls, spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)


def shop_screen(page: ft.Page, device_id: str, session=None, on_home=None):
    return ShopScreen(page=page, device_id=device_id, session=session, on_home=on_home)
