"""Visible, deterministic robot rewards and their permanent team abilities."""

from dataclasses import dataclass, replace
from robot_designs import DESIGNS

MAX_ROBOT_LEVEL = 12
RARITIES = {
    "common": ("Обычный", "#4786D9"),
    "rare": ("Редкий", "#9565D9"),
    "epic": ("Эпический", "#E36C67"),
    "legendary": ("Легендарный", "#DC9B2A"),
    "mythic": ("Мифический", "#DC5796"),
}


@dataclass(frozen=True)
class Robot:
    id: str
    name: str
    role: str
    story: str
    level: int
    egg_price: int
    taps: int
    training_price: int
    egg: str
    color: str
    click: int = 0
    auto: int = 0
    offline: int = 0
    orders: int = 0
    rarity: str = "common"
    hatch_seconds: int = 120
    mobility: str = "tracks"

    @property
    def image(self):
        return f"art/portraits/{self.id}.svg"

    @property
    def egg_image(self):
        return f"art/egg_{self.egg}.webp"

    def ability(self, level=1):
        parts = []
        if self.click:
            parts.append(f"+{self.click * level} за касание")
        if self.auto:
            parts.append(f"+{self.auto * level} монет/с")
        if self.offline:
            parts.append(f"+{self.offline * level} монет/мин отдыха")
        if self.orders:
            parts.append(f"+{self.orders * level}% к заказам")
        return " · ".join(parts)


ROBOTS = (
    Robot(
        "spark",
        "Искра",
        "Мастер касаний",
        "Маленький друг с большим любопытством.",
        1,
        0,
        12,
        60,
        "starter",
        "#EFA74A",
        click=1,
        hatch_seconds=0,
    ),
    Robot(
        "volt",
        "Вольт",
        "Энергия команды",
        "Летает по мастерской и собирает монеты.",
        3,
        180,
        35,
        150,
        "tech",
        "#45BFE6",
        auto=1,
        mobility="hover",
    ),
    Robot(
        "flora",
        "Флора",
        "Хранитель отдыха",
        "Заботится о мастерской, пока ты отдыхаешь.",
        6,
        450,
        60,
        220,
        "tech",
        "#55BA9E",
        offline=2,
        rarity="rare",
        hatch_seconds=300,
        mobility="legs",
    ),
    Robot(
        "forge",
        "Кузя",
        "Мастер заказов",
        "Любое изобретение доводит до блеска.",
        10,
        1100,
        90,
        400,
        "tech",
        "#E9875E",
        orders=15,
        rarity="epic",
        hatch_seconds=600,
    ),
    Robot(
        "nova",
        "Нова",
        "Звёздный изобретатель",
        "Приносит в команду идеи из далёких миров.",
        16,
        3000,
        140,
        650,
        "cosmic",
        "#B188F3",
        click=3,
        auto=2,
        rarity="legendary",
        hatch_seconds=1200,
        mobility="hover",
    ),
    Robot(
        "glacier",
        "Норд",
        "Ледяной разведчик",
        "Находит детали там, где другие видят только иней.",
        8,
        750,
        75,
        300,
        "tech",
        "#68BCD9",
        auto=1,
        offline=1,
        rarity="rare",
        hatch_seconds=420,
        mobility="hover",
    ),
    Robot(
        "aegis",
        "Бастион",
        "Щит мастерской",
        "Большой защитник с мягким характером и крепкой бронёй.",
        13,
        2000,
        110,
        520,
        "tech",
        "#D96B61",
        click=1,
        orders=12,
        rarity="epic",
        hatch_seconds=900,
        mobility="tracks",
    ),
    Robot(
        "solar",
        "Гелиос",
        "Солнечный хранитель",
        "Его кольцо собирает свет и превращает его в новые идеи.",
        22,
        7500,
        180,
        950,
        "cosmic",
        "#EFAB4D",
        click=2,
        auto=3,
        rarity="mythic",
        hatch_seconds=1800,
        mobility="hover",
    ),
)
_old_ids = {r.id for r in ROBOTS}
ROBOTS = tuple(replace(r,mobility=DESIGNS[r.id]['mobility']) for r in ROBOTS)
ROBOTS += tuple(Robot(d['id'], d['name'], d['ultimate'], d['strength'] + '. ' + d['weakness'] + '.',
                      d['unlock'], 150*d['unlock'], 50+5*d['unlock'], 80+20*d['unlock'],
                      'cosmic' if d['rarity'] in {'legendary','mythic'} else 'tech', d['color'],
                      rarity=d['rarity'], hatch_seconds=120+40*d['unlock'], mobility=d['mobility'])
                for d in DESIGNS.values() if d['id'] not in _old_ids)
ROBOT_BY_ID = {robot.id: robot for robot in ROBOTS}


def training_price(robot: Robot, level: int) -> int:
    return robot.training_price * 3 ** max(0, min(MAX_ROBOT_LEVEL, level) - 1)
