"""Deterministic game rules shared by the UI, saves, and background sync."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from progression import perform_extra, refresh_day
from robot_arena import BATTLE_ENERGY, new_battle, restore_battle, take_turn
from robot_catalog import MAX_ROBOT_LEVEL, ROBOT_BY_ID, ROBOTS, training_price

MAX_VALUE = 9_000_000_000_000_000
PALETTES = ("#4E7BF2", "#248E83", "#BD6483", "#9063CE")


def number(value, default=0, maximum=MAX_VALUE):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return max(0, min(maximum, int(value)))


def threshold(level: int) -> int:
    return 5 * level * (level + 1)


def upgrade_price(base: int, power: int) -> int:
    return min(MAX_VALUE, base * 2 ** min(50, max(0, power)))


def compact(value: int | float) -> str:
    value = max(0, value)
    for divider, suffix in ((1e12, "трлн"), (1e9, "млрд"), (1e6, "млн"), (1e3, "тыс")):
        if value >= divider:
            return f"{value / divider:.1f}".rstrip("0").rstrip(".") + " " + suffix
    return str(int(value))


@dataclass(frozen=True)
class CareerStage:
    title: str
    level: int
    caption: str
    color: str


STAGES = (
    CareerStage(
        "Первые идеи", 1, "Большие открытия начинаются с маленького шага", "#DDEBFF"
    ),
    CareerStage(
        "Уютный уголок", 3, "У помощника появилось своё место для работы", "#DBF3E9"
    ),
    CareerStage("Мастерская", 6, "Новые инструменты — новые возможности", "#FFF0D4"),
    CareerStage("Лаборатория", 10, "Пора собирать собственные изобретения", "#EAE2FF"),
    CareerStage("Команда мечты", 16, "Хорошие идеи объединяют друзей", "#FFE4EA"),
    CareerStage("Город идей", 25, "Твоя мастерская выросла в целый мир", "#DDF2FB"),
)


@dataclass(frozen=True)
class Order:
    id: str
    title: str
    seconds: int
    energy: int
    reward: int
    stage: int = 0


ORDERS = (
    Order("lamp", "Собрать фонарик", 45, 15, 30),
    Order("scooter", "Починить самокат", 120, 25, 85, 1),
    Order("robot", "Создать мини-робота", 240, 40, 190, 2),
    Order("beacon", "Собрать маяк команды", 360, 50, 285, 3),
    Order("solar", "Настроить солнечную станцию", 600, 65, 460, 4),
)


@dataclass(frozen=True)
class Goal:
    id: str
    title: str
    attribute: str
    target: int
    reward: int


GOALS = (
    Goal("hatch1", "Открыть первого робота", "robot_count", 1, 35),
    Goal("tap20", "Первые 20 касаний", "manual_taps", 20, 25),
    Goal("feed3", "Покормить роботов 3 раза", "feedings", 3, 80),
    Goal("arena1", "Первая победа на арене", "arena_wins", 1, 100),
    Goal("upgrade1", "Купить улучшение", "purchases", 1, 40),
    Goal("job1", "Выполнить первый заказ", "jobs_done", 1, 50),
    Goal("robot1", "Включить автосборщик", "base_auto_click_power", 1, 70),
    Goal("charge1", "Подзарядить помощника", "charges", 1, 30),
    Goal("tap100", "Сделать 100 касаний", "manual_taps", 100, 100),
    Goal("level5", "Достичь уровня 5", "level", 5, 130),
    Goal("job3", "Выполнить 3 заказа", "jobs_done", 3, 180),
    Goal("offline1", "Наладить доход вне игры", "offline_income_power", 1, 150),
    Goal(
        "robot3", "Улучшить автосборщик до 3-го уровня", "base_auto_click_power", 3, 200
    ),
    Goal("level10", "Достичь уровня 10", "level", 10, 350),
    Goal("power10", "Прокачать силу касания до 10", "base_click_power", 10, 500),
    Goal("team3", "Собрать команду из 3 роботов", "robot_count", 3, 400),
    Goal("train3", "Улучшить роботов 3 раза", "robot_trainings", 3, 300),
    Goal("feed15", "Угостить команду 15 раз", "feedings", 15, 120),
    Goal("arena5", "Пять побед на арене", "arena_wins", 5, 180),
    Goal("lamp5", "Собрать 5 фонариков", "lamps_built", 5, 160),
    Goal("box1", "Открыть бокс припасов", "crates_opened", 1, 80),
    Goal("daily3", "Три награды целей дня", "dailies_done", 3, 160),
    Goal("tap500", "500 касаний для команды", "manual_taps", 500, 200),
    Goal("arena10", "Десять побед на арене", "arena_wins", 10, 300),
    Goal("projects10", "Завершить 10 проектов", "jobs_done", 10, 240),
    Goal("team5", "Собрать 5 разных роботов", "robot_count", 5, 450),
    Goal("box5", "Открыть 5 боксов", "crates_opened", 5, 180),
    Goal("feed100", "Сто угощений друзьям", "feedings", 100, 350),
    Goal("arena20", "Двадцать побед на арене", "arena_wins", 20, 550),
    Goal("team8", "Полная команда из 8 роботов", "robot_count", 8, 850),
    Goal("arsenal3", "Собрать три вида оружия", "weapon_count", 3, 180),
    Goal("arsenal10", "Полный арсенал", "weapon_count", 10, 700),
    Goal("weapons15", "Пятнадцать улучшений оружия", "weapon_upgrades", 15, 500),
    Goal("weapons50", "Мастер вооружения", "weapon_upgrades", 50, 1200),
    Goal("cup3", "Выиграть кубок ботов", "tournament_best", 3, 300),
)


@dataclass
class GameState:
    level: int = 1
    coin: int = 0
    session_taps: int = 0
    base_click_power: int = 1
    double_click_price: int = 10
    base_auto_click_power: int = 0
    auto_click_price: int = 50
    offline_income_power: int = 0
    offline_income_price: int = 100
    boost_level: int = 0
    boost_price: int = 20
    boost_end_at: float = 0
    username: str = ""
    experience: int = 0
    manual_taps: int = 0
    purchases: int = 0
    jobs_done: int = 0
    charges: int = 0
    energy: float = 100
    work_id: str = ""
    work_started_at: float = 0
    work_end_at: float = 0
    work_reward: int = 0
    claimed_goals: list[str] = field(default_factory=list)
    contracts: int = 0
    play_seconds: float = 0
    auto_carry: float = 0
    auto_xp_carry: float = 0
    last_active_at: float = 0
    modified_at: float = 0
    accent: str = PALETTES[0]
    robot_levels: dict[str, int] = field(default_factory=dict)
    active_robot: str = ""
    egg_id: str = "spark"
    egg_started_taps: int = 0
    robot_trainings: int = 0
    food: int = 0
    feedings: int = 0
    robot_xp: dict[str, int] = field(default_factory=dict)
    robot_energy: dict[str, int] = field(default_factory=dict)
    arena_stage: int = 0
    arena_wins: int = 0
    battles_played: int = 0
    battle_serial: int = 0
    battle: dict = field(default_factory=dict)
    robot_charge_carry: float = 0
    parts: int = 0
    crates_opened: int = 0
    craft_counts: dict[str, int] = field(default_factory=dict)
    egg_stock: dict[str, int] = field(default_factory=dict)
    egg_started_at: float = 0
    egg_ready_at: float = 0
    avatar_id: str = "starter"
    daily_day: int = 0
    daily_base: dict[str, int] = field(default_factory=dict)
    daily_claimed: list[str] = field(default_factory=list)
    dailies_done: int = 0
    reward_tokens: list[str] = field(default_factory=list)
    reward_day: int = 0
    reward_count: int = 0
    reward_last_at: float = 0
    video_boost_end_at: float = 0
    lamp_on: bool = True
    tutorial_seen: bool = False
    weapon_levels: dict[str, int] = field(default_factory=dict)
    loadouts: dict[str, list[str]] = field(default_factory=dict)
    weapon_upgrades: int = 0
    rare_parts: int = 0
    arena_difficulty: str = "normal"
    weekly: dict = field(default_factory=dict)
    tournament: dict = field(default_factory=dict)
    collection: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict | None) -> GameState:
        if not isinstance(data, dict):
            return cls()
        state = cls()
        integer_fields = (
            "level",
            "coin",
            "session_taps",
            "base_click_power",
            "double_click_price",
            "base_auto_click_power",
            "auto_click_price",
            "offline_income_power",
            "offline_income_price",
            "boost_level",
            "boost_price",
            "experience",
            "manual_taps",
            "purchases",
            "jobs_done",
            "charges",
            "work_reward",
            "contracts",
            "egg_started_taps",
            "robot_trainings",
            "food",
            "feedings",
            "arena_stage",
            "arena_wins",
            "battles_played",
            "battle_serial",
            "parts",
            "crates_opened",
            "daily_day",
            "dailies_done",
            "reward_day",
            "reward_count",
        )
        aliases = {
            "session_taps": "taps",
            "play_seconds": "time",
            "last_active_at": "last_update",
        }
        for name in integer_fields:
            value = data.get(
                name, data.get(aliases.get(name, ""), getattr(state, name))
            )
            setattr(state, name, number(value, getattr(state, name)))
        state.level = min(40_000_000, max(1, state.level))
        state.base_click_power = max(1, state.base_click_power)
        if "double_click_price" not in data:
            state.double_click_price = upgrade_price(10, state.base_click_power - 1)
        if "auto_click_price" not in data:
            state.auto_click_price = upgrade_price(50, state.base_auto_click_power)
        if "offline_income_price" not in data:
            state.offline_income_price = upgrade_price(100, state.offline_income_power)
        for name in (
            "boost_end_at",
            "work_started_at",
            "work_end_at",
            "play_seconds",
            "auto_carry",
            "auto_xp_carry",
            "last_active_at",
            "modified_at",
            "energy",
            "robot_charge_carry",
            "egg_started_at",
            "egg_ready_at",
            "reward_last_at",
            "video_boost_end_at",
        ):
            value = data.get(
                name, data.get(aliases.get(name, ""), getattr(state, name))
            )
            if (
                isinstance(value, (float, int))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ):
                setattr(state, name, max(0.0, float(value)))
        state.energy = min(100.0, state.energy)
        state.auto_carry = min(0.999999999, state.auto_carry)
        state.auto_xp_carry = min(0.999999999, state.auto_xp_carry)
        state.robot_charge_carry = min(44.999999, state.robot_charge_carry)
        state.username = str(data.get("username") or "").strip()[:24]
        state.work_id = str(data.get("work_id", ""))
        if state.work_id not in {order.id for order in ORDERS}:
            state.work_id = ""
            state.work_end_at = 0
        claimed = data.get("claimed_goals", [])
        if isinstance(claimed, list):
            state.claimed_goals = list(dict.fromkeys(str(item) for item in claimed))[
                : len(GOALS)
            ]
        if data.get("accent") in PALETTES:
            state.accent = data["accent"]
        robots = data.get("robot_levels")
        if isinstance(robots, dict):
            state.robot_levels = {
                robot.id: number(robots[robot.id], maximum=MAX_ROBOT_LEVEL)
                for robot in ROBOTS
                if robot.id in robots and number(robots[robot.id]) > 0
            }
        active = data.get("active_robot")
        state.active_robot = (
            active
            if isinstance(active, str) and active in state.robot_levels
            else next(iter(state.robot_levels), "")
        )
        egg = data.get("egg_id", "spark" if "spark" not in state.robot_levels else "")
        state.egg_id = (
            egg
            if isinstance(egg, str)
            and egg in ROBOT_BY_ID
            and egg not in state.robot_levels
            else ""
        )
        for identity in state.robot_levels:
            xp = data.get("robot_xp")
            energy = data.get("robot_energy")
            state.robot_xp[identity] = (
                number(xp.get(identity), maximum=100000) if isinstance(xp, dict) else 0
            )
            state.robot_energy[identity] = (
                number(energy.get(identity), 70, maximum=100)
                if isinstance(energy, dict)
                else 70
            )
        state.battle = restore_battle(data.get("battle"))
        if state.battle.get("robot_id") not in state.robot_levels:
            state.battle = {}
        state.battle_serial = max(state.battle_serial, state.battle.get("id", 0))
        for name, allowed in (
            ("craft_counts", {order.id for order in ORDERS}),
            ("egg_stock", set(ROBOT_BY_ID) - set(state.robot_levels) - {state.egg_id}),
            ("daily_base", {"manual_taps", "feedings", "jobs_done"}),
        ):
            raw = data.get(name, {})
            if isinstance(raw, dict):
                setattr(
                    state,
                    name,
                    {
                        key: number(
                            value, maximum=1 if name == "egg_stock" else MAX_VALUE
                        )
                        for key, value in raw.items()
                        if key in allowed
                    },
                )
        raw = data.get("daily_claimed", [])
        if isinstance(raw, list):
            state.daily_claimed = list(
                dict.fromkeys(
                    key
                    for key in raw
                    if isinstance(key, str) and key in {"taps", "care", "project"}
                )
            )
        tokens = data.get("reward_tokens", [])
        if isinstance(tokens, list):
            state.reward_tokens = list(
                dict.fromkeys(token[:80] for token in tokens if isinstance(token, str))
            )[-64:]
        state.reward_count = min(4, state.reward_count)
        state.lamp_on = data.get("lamp_on", True) is not False
        state.tutorial_seen = data.get("tutorial_seen", False) is True
        from progression import avatars

        desired_avatar = data.get("avatar_id", "starter")
        if isinstance(desired_avatar, str) and any(
            item.id == desired_avatar and item.unlocked for item in avatars(state)
        ):
            state.avatar_id = desired_avatar
        if not state.egg_id:
            state.egg_ready_at = state.egg_started_at = 0
        # An older save has no XP. Preserve its level and progress instead of
        # deriving a lower level from the balance after previous purchases.
        state.experience = max(state.experience, threshold(state.level - 1))
        state.modified_at = state.modified_at or state.last_active_at
        from armory import restore

        restore(state, data)
        from collection_progress import restore as restore_collection
        restore_collection(state, data.get('collection'))
        return state

    def to_dict(self) -> dict:
        return asdict(self)

    def clone(self) -> GameState:
        return self.from_dict(self.to_dict())

    @property
    def stage_index(self) -> int:
        return max(
            index for index, stage in enumerate(STAGES) if self.level >= stage.level
        )

    @property
    def weapon_count(self):
        return len(self.weapon_levels)

    @property
    def tournament_best(self):
        return self.tournament.get("best", 0)

    @property
    def stage(self) -> CareerStage:
        return STAGES[self.stage_index]

    @property
    def level_progress(self) -> float:
        start, end = threshold(self.level - 1), threshold(self.level)
        return max(0.0, min(1.0, (self.experience - start) / max(1, end - start)))

    def multiplier(self, now: float) -> float:
        return (
            min(3.0, 1 + 0.15 * self.boost_level + 0.02 * (self.level - 1))
            if now < self.boost_end_at
            else 1.0
        )

    @property
    def robot_count(self) -> int:
        return len(self.robot_levels)

    def robot_bonus(self, attribute: str) -> int:
        return sum(
            getattr(ROBOT_BY_ID[identity], attribute) * level
            for identity, level in self.robot_levels.items()
        )

    @property
    def auto_base_power(self) -> int:
        return self.base_auto_click_power + self.robot_bonus("auto")

    @property
    def rest_power(self) -> int:
        return self.offline_income_power + self.robot_bonus("offline")

    @property
    def egg_progress(self) -> int:
        robot = ROBOT_BY_ID.get(self.egg_id)
        return (
            min(robot.taps, max(0, self.manual_taps - self.egg_started_taps))
            if robot
            else 0
        )

    @property
    def egg_ready(self) -> bool:
        robot = ROBOT_BY_ID.get(self.egg_id)
        return robot is not None and (
            max(self.last_active_at, self.modified_at) >= self.egg_ready_at
            if self.egg_ready_at
            else self.egg_progress >= robot.taps
        )

    def egg_is_ready(self, now):
        return bool(self.egg_id) and (
            now >= self.egg_ready_at if self.egg_ready_at else self.egg_ready
        )

    @property
    def lamps_built(self):
        return self.craft_counts.get("lamp", 0)

    def click_power(self, now: float) -> int:
        base = self.base_click_power + self.robot_bonus("click")
        return (
            max(base + 1, round(base * self.multiplier(now)))
            if now < self.boost_end_at
            else base
        )

    def auto_power(self, now: float) -> int:
        base = self.auto_base_power
        if not base:
            return 0
        return (
            max(base + 1, round(base * self.multiplier(now)))
            if now < self.boost_end_at
            else base
        )

    def earn(self, coins: int, xp: int | None = None):
        self.coin = min(MAX_VALUE, self.coin + max(0, coins))
        self.experience = min(
            MAX_VALUE, self.experience + max(0, coins if xp is None else xp)
        )
        earned_level = (math.isqrt(1 + 4 * self.experience // 5) - 1) // 2 + 1
        self.level = max(self.level, earned_level)

    def cloud_payload(self, device_id: str, now: float) -> dict:
        return {
            "id": device_id,
            "level": self.level,
            "taps": self.session_taps,
            "time": int(self.play_seconds),
            "username": self.username,
            "last_update": now,
            "coin": self.coin,
            "base_click_power": self.base_click_power,
            "double_click_price": self.double_click_price,
            "base_auto_click_power": self.base_auto_click_power,
            "offline_income_power": self.offline_income_power,
            "boost_level": self.boost_level,
            "boost_price": self.boost_price,
        }


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str = ""
    coins: int = 0


def tap(state: GameState, now: float, count: int = 1) -> ActionResult:
    count = number(count, maximum=MAX_VALUE)
    refresh_day(state, now)
    gain = min(MAX_VALUE, state.click_power(now) * count)
    if now < state.video_boost_end_at:
        gain = min(MAX_VALUE, gain * 2)
    if state.egg_id and state.egg_ready_at > now:
        state.egg_ready_at = max(now, state.egg_ready_at - count * 2)
    state.food = min(MAX_VALUE, state.food + gain)
    state.manual_taps = min(MAX_VALUE, state.manual_taps + count)
    state.session_taps = min(MAX_VALUE, state.session_taps + count)
    state.earn(gain, count)
    state.modified_at = now
    return ActionResult(True, coins=gain)


def advance(state: GameState, now: float) -> bool:
    if not state.last_active_at:
        state.last_active_at = now
        return False
    if now <= state.last_active_at:
        return False
    elapsed = now - state.last_active_at
    state.last_active_at = now
    if elapsed > 5:
        return offline_income(state, elapsed, now) > 0
    if elapsed <= 0:
        return False
    previous = state.to_dict()
    state.play_seconds += elapsed
    state.energy = min(100.0, state.energy + elapsed / 8)
    recharge_robots(state, elapsed)
    boosted = min(elapsed, max(0.0, state.boost_end_at - (now - elapsed)))
    accrued = state.auto_carry + state.auto_base_power * (elapsed - boosted)
    accrued += (
        state.auto_power(min(now, state.boost_end_at - 0.001)) * boosted
        if boosted
        else 0
    )
    gain = int(accrued + 1e-9)
    state.auto_carry = max(0.0, accrued - gain)
    accrued_xp = state.auto_xp_carry + (elapsed if state.auto_base_power else 0)
    xp = min(gain, int(accrued_xp + 1e-9))
    state.auto_xp_carry = max(0.0, accrued_xp - xp)
    if gain:
        state.session_taps = min(MAX_VALUE, state.session_taps + gain)
        state.earn(gain, xp)
        state.modified_at = now
    return state.to_dict() != previous


def offline_income(state: GameState, elapsed: float, now: float) -> int:
    elapsed = min(24 * 3600, max(0.0, elapsed))
    gain = int(elapsed // 60) * state.rest_power
    state.energy = min(100.0, state.energy + elapsed / 8)
    recharge_robots(state, elapsed)
    state.last_active_at = now
    if gain:
        state.session_taps = min(MAX_VALUE, state.session_taps + gain)
        state.earn(gain, min(gain, int(elapsed // 300)))
        state.modified_at = now
    return gain


def buy(state: GameState, kind: str, now: float) -> ActionResult:
    fields = {
        "click": "double_click_price",
        "auto": "auto_click_price",
        "offline": "offline_income_price",
        "boost": "boost_price",
    }
    if kind not in fields:
        return ActionResult(False, "Такого улучшения нет")
    if kind == "boost" and state.boost_end_at > now:
        return ActionResult(False, "Суперрежим уже работает")
    price_field = fields[kind]
    price = getattr(state, price_field)
    if state.coin < price:
        return ActionResult(False, "Нужно ещё немного монет")
    state.coin -= price
    state.purchases += 1
    if kind == "click":
        state.base_click_power += 1
    elif kind == "auto":
        state.base_auto_click_power += 1
    elif kind == "offline":
        state.offline_income_power += 1
    else:
        state.boost_level += 1
        state.boost_end_at = now + 20
    setattr(
        state,
        price_field,
        min(MAX_VALUE, int(120 * 1.8 ** min(50, state.boost_level)))
        if kind == "boost"
        else min(MAX_VALUE, price * 2),
    )
    state.modified_at = now
    return ActionResult(
        True, "Улучшение готово!" if kind != "boost" else "Суперрежим на 20 секунд!"
    )


def order_reward(state: GameState, order: Order) -> int:
    base = order.reward + state.stage_index * (order.reward // 3)
    return base * (100 + state.robot_bonus("orders")) // 100


def start_order(state: GameState, order_id: str, now: float) -> ActionResult:
    order = next((item for item in ORDERS if item.id == order_id), None)
    if order is None or state.stage_index < order.stage:
        return ActionResult(False, "Этот заказ откроется в следующей мастерской")
    if state.work_id:
        return ActionResult(False, "Сначала забери награду за текущий заказ")
    if state.energy < order.energy:
        return ActionResult(False, "Помощнику нужна подзарядка")
    state.energy -= order.energy
    state.work_id = order.id
    state.work_started_at = now
    state.work_end_at = now + order.seconds
    state.work_reward = order_reward(state, order)
    state.modified_at = now
    return ActionResult(True, "Заказ начат. Можно продолжать собирать монеты!")


def collect_order(state: GameState, now: float) -> ActionResult:
    if not state.work_id or now < state.work_end_at:
        return ActionResult(False, "Помощник ещё работает")
    reward = state.work_reward
    identity = state.work_id
    state.work_id = ""
    state.work_started_at = state.work_end_at = 0
    state.work_reward = 0
    state.jobs_done += 1
    state.craft_counts[identity] = state.craft_counts.get(identity, 0) + 1
    state.parts = min(
        MAX_VALUE, state.parts + (2 if identity in {"lamp", "scooter"} else 3)
    )
    state.earn(reward, max(5, reward // 2))
    state.modified_at = now
    return ActionResult(True, f"Заказ выполнен: +{compact(reward)} монет!", reward)


def charge_price(state: GameState) -> int:
    return 12 + state.stage_index * 6


def charge(state: GameState, now: float) -> ActionResult:
    if state.energy >= 100:
        return ActionResult(False, "Заряд уже полный")
    price = charge_price(state)
    if state.coin < price:
        return ActionResult(False, "Нужно ещё немного монет")
    state.coin -= price
    state.energy = min(100.0, state.energy + 40)
    state.charges += 1
    state.modified_at = now
    return ActionResult(True, "Помощник снова полон сил!")


def active_goals(state: GameState) -> list[Goal]:
    remaining = [goal for goal in GOALS if goal.id not in state.claimed_goals]
    if remaining:
        return remaining[:3]
    return [
        Goal(
            f"contract{state.contracts}",
            "Мастерский заказ",
            "jobs_done",
            5 + state.contracts * 3,
            350 + state.contracts * 150,
        )
    ]


def claim_goal(state: GameState, goal_id: str, now: float) -> ActionResult:
    goal = next((item for item in active_goals(state) if item.id == goal_id), None)
    if goal is None or getattr(state, goal.attribute) < goal.target:
        return ActionResult(False, "До цели осталось совсем немного")
    if goal.id.startswith("contract"):
        state.contracts += 1
    else:
        state.claimed_goals.append(goal.id)
    state.earn(goal.reward, max(5, goal.reward // 3))
    state.parts = min(MAX_VALUE, state.parts + 1)
    state.modified_at = now
    return ActionResult(
        True, f"Цель достигнута: +{compact(goal.reward)} монет!", goal.reward
    )


def incubate_robot(state: GameState, robot_id: str, now: float) -> ActionResult:
    robot = ROBOT_BY_ID.get(robot_id)
    if robot is None:
        return ActionResult(False, "Такого робота нет")
    if robot_id in state.robot_levels:
        return ActionResult(False, "Этот робот уже в команде")
    if state.egg_id:
        return ActionResult(False, "Сначала открой яйцо в мастерской")
    if state.egg_stock.get(robot_id):
        return ActionResult(False, "Это яйцо уже в хранилище — помести его в инкубатор")
    if state.level < robot.level:
        return ActionResult(False, f"Яйцо откроется на уровне {robot.level}")
    if state.coin < robot.egg_price:
        return ActionResult(False, "Нужно ещё немного монет")
    state.coin -= robot.egg_price
    state.egg_id = robot_id
    state.egg_started_taps = state.manual_taps
    state.egg_started_at = now
    state.egg_ready_at = now + robot.hatch_seconds if robot.hatch_seconds else 0
    state.modified_at = now
    return ActionResult(True, f"В инкубаторе — {robot.name}. Касания ускоряют таймер")


def hatch_robot(state: GameState, now: float) -> ActionResult:
    robot = ROBOT_BY_ID.get(state.egg_id)
    if robot is None or robot.id in state.robot_levels or not state.egg_is_ready(now):
        return ActionResult(False, "Заряжай яйцо касаниями, и робот появится")
    state.robot_levels[robot.id] = 1
    state.robot_xp[robot.id] = 0
    state.robot_energy[robot.id] = 70
    state.active_robot = robot.id
    state.egg_id = ""
    state.egg_started_taps = 0
    state.egg_started_at = state.egg_ready_at = 0
    if state.avatar_id == "starter":
        state.avatar_id = f"robot:{robot.id}"
    state.earn(0, 20)
    state.modified_at = now
    return ActionResult(True, f"{robot.name} в команде! {robot.ability()}")


def train_robot(state: GameState, robot_id: str, now: float) -> ActionResult:
    robot = ROBOT_BY_ID.get(robot_id)
    level = state.robot_levels.get(robot_id, 0)
    if robot is None or not level:
        return ActionResult(False, "Сначала открой этого робота")
    if level >= MAX_ROBOT_LEVEL:
        return ActionResult(False, "Робот достиг максимального уровня")
    price = training_price(robot, level)
    if state.coin < price:
        return ActionResult(False, "Нужно ещё немного монет")
    state.coin -= price
    state.robot_levels[robot_id] += 1
    state.robot_trainings += 1
    state.purchases += 1
    state.modified_at = now
    return ActionResult(
        True, f"{robot.name}: уровень {level + 1}! {robot.ability(level + 1)}"
    )


def perform(state: GameState, name: str, args: list, now: float) -> ActionResult:
    from collection_progress import perform_collection, record_activity
    before = dict(wins=state.arena_wins, jobs=state.jobs_done, training=state.robot_trainings, taps=state.manual_taps)
    result = perform_collection(state, name, args, now)
    if result is None:
        result = _perform_core(state, name, args, now)
    if result.ok:
        record_activity(state, name, before, now)
    return result


def _perform_core(state: GameState, name: str, args: list, now: float) -> ActionResult:
    from armory import perform_armory

    equipment_result = perform_armory(state, name, args, now)
    if equipment_result is not None:
        if equipment_result.ok:
            state.modified_at = now
        return equipment_result
    extra = perform_extra(state, name, args, now)
    if extra is not None:
        return extra
    if name == "tap":
        return tap(state, now, args[0] if args else 1)
    if name == "buy":
        return buy(state, args[0], now)
    if name == "order":
        return start_order(state, args[0], now)
    if name == "collect":
        return collect_order(state, now)
    if name == "charge":
        return charge(state, now)
    if name == "goal":
        return claim_goal(state, args[0], now)
    if name == "incubate":
        return incubate_robot(state, args[0], now)
    if name == "hatch":
        return hatch_robot(state, now)
    if name == "train_robot":
        return train_robot(state, args[0], now)
    if name == "feed":
        return feed_robot(state, args[0], now)
    if name == "battle_start":
        return start_battle(state, args[0] if args else state.active_robot, now)
    if name == "battle_turn":
        return battle_turn(state, args[0], args[1], args[2], now)
    if name == "battle_leave":
        if state.battle.get("result") == "active":
            state.battle["result"] = "left"
            state.modified_at = now
            return ActionResult(True, "Спарринг завершён. Робот остаётся в команде")
        return ActionResult(False)
    if name == "select_robot" and args[0] in state.robot_levels:
        state.active_robot = args[0]
        state.modified_at = now
        return ActionResult(
            True,
            f"{ROBOT_BY_ID[args[0]].name} в мастерской. Вся команда продолжает помогать",
        )
    if name == "theme" and args[0] in PALETTES:
        state.accent = args[0]
        state.modified_at = now
        return ActionResult(True)
    if name == "rename":
        username = str(args[0]).strip()
        if not 2 <= len(username) <= 20:
            return ActionResult(False, "Имя должно содержать от 2 до 20 символов")
        if username == state.username:
            return ActionResult(True)
        if state.coin < 500:
            return ActionResult(False, "Для нового имени нужно 500 монет")
        state.coin -= 500
        state.username = username
        state.modified_at = now
        return ActionResult(True, "Новое имя сохранено")
    return ActionResult(False, "Неизвестное действие")


def feeding_target(level):
    return 40 + 20 * level + 10 * level * level


def recharge_robots(state, seconds):
    total = state.robot_charge_carry + min(24 * 3600, max(0, seconds))
    charge = int(total // 45)
    state.robot_charge_carry = total % 45
    if charge:
        for identity in state.robot_levels:
            state.robot_energy[identity] = min(
                100, state.robot_energy.get(identity, 70) + charge
            )


def add_robot_xp(state, robot_id, amount):
    level = state.robot_levels[robot_id]
    xp = state.robot_xp.get(robot_id, 0) + amount
    while level < MAX_ROBOT_LEVEL and xp >= feeding_target(level):
        xp -= feeding_target(level)
        level += 1
        state.robot_trainings += 1
    state.robot_levels[robot_id] = level
    state.robot_xp[robot_id] = xp if level < MAX_ROBOT_LEVEL else 0


def feed_robot(state, robot_id, now):
    if robot_id not in state.robot_levels:
        return ActionResult(False, "Сначала открой робота")
    if state.food < 5:
        return ActionResult(False, "Собери 5 порций корма касаниями")
    energy = state.robot_energy.get(robot_id, 70)
    if energy >= 100 and state.robot_levels[robot_id] >= MAX_ROBOT_LEVEL:
        return ActionResult(False, "Робот сыт и готов к спаррингу")
    state.food -= 5
    state.feedings += 1
    state.robot_energy[robot_id] = min(100, energy + 18)
    previous = state.robot_levels[robot_id]
    add_robot_xp(state, robot_id, 2)
    state.modified_at = now
    robot = ROBOT_BY_ID[robot_id]
    message = f"{robot.name} подкрепился: +{min(18, 100 - energy)} заряда"
    if previous < MAX_ROBOT_LEVEL:
        message += " и +2 опыта"
    if previous != state.robot_levels[robot_id]:
        message = f"{robot.name} вырос до уровня {state.robot_levels[robot_id]}!"
    return ActionResult(True, message)


def start_battle(state, robot_id, now):
    if state.battle.get("result") == "active":
        return ActionResult(False, "Сначала заверши текущий спарринг")
    if robot_id not in state.robot_levels:
        return ActionResult(False, "Открой первого робота, чтобы выйти на арену")
    energy = state.robot_energy.get(robot_id, 70)
    if energy < BATTLE_ENERGY:
        return ActionResult(False, "Покорми робота: для спарринга нужно 20 заряда")
    state.robot_energy[robot_id] = energy - BATTLE_ENERGY
    state.battle_serial += 1
    state.battles_played += 1
    state.battle = new_battle(
        robot_id, state.robot_levels[robot_id], state.arena_stage + (state.tournament.get("wins",0) if state.tournament.get("active") else 0), state.battle_serial
    )
    from armory import equip_battle

    equip_battle(state, state.battle)
    state.modified_at = now
    return ActionResult(True, "Спарринг начался!")


def battle_turn(state, action, battle_id, expected_turn, now):
    result = take_turn(state.battle, action, battle_id, expected_turn)
    if not result.ok:
        return ActionResult(False, result.message)
    reward = 0
    if result.finished:
        robot_id = state.battle["robot_id"]
        if state.battle["result"] == "win":
            reward = state.battle["reward"]
            state.earn(reward, 15)
            state.food = min(MAX_VALUE, state.food + 4)
            state.arena_wins += 1
            state.parts = min(
                MAX_VALUE, state.parts + 3 + (2 if state.battle.get("boss") else 0)
            )
            if state.battle.get("mode") == "tournament":
                state.tournament["wins"] = min(3, state.tournament.get("wins", 0) + 1)
                state.tournament["best"] = max(
                    state.tournament.get("best", 0), state.tournament["wins"]
                )
                if state.tournament["wins"] == 3:
                    state.tournament["active"] = False
                    if "cup" not in state.tournament.setdefault("claimed", []):
                        state.tournament["claimed"].append("cup")
                        state.rare_parts += 4
                        state.earn(350, 20)
            else:
                state.arena_stage += 1
            if state.battle.get("boss"):
                state.rare_parts += 1
            add_robot_xp(state, robot_id, 6)
        else:
            if state.battle.get("mode") == "tournament":
                state.tournament["active"] = False
            add_robot_xp(state, robot_id, 1)
    state.modified_at = now
    return ActionResult(
        True,
        f"Победа! +{reward} монет, +4 корма и опыт роботу"
        if reward
        else result.message,
        reward,
    )
