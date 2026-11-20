"""Visible rewards, daily goals, stored eggs, profile icons and video bonuses."""

from dataclasses import dataclass

from robot_catalog import MAX_ROBOT_LEVEL, ROBOT_BY_ID, ROBOTS

DAY = 86400
VIDEO_LIMIT = 4
VIDEO_COOLDOWN = 60
DAILY_SPECS = (
    ("taps", "100 касаний", "manual_taps", 100, 35, 8, 2),
    ("care", "Покормить команду 5 раз", "feedings", 5, 30, 5, 2),
    ("project", "Завершить один проект", "jobs_done", 1, 40, 6, 3),
)


@dataclass(frozen=True)
class Avatar:
    id: str
    title: str
    image: str
    unlocked: bool
    requirement: str = ""


def avatars(state):
    result = [
        Avatar("starter", "Первое открытие", "art/icons/profile.svg", True),
        Avatar("egg:starter", "Таинственное яйцо", "art/egg_starter.webp", True),
    ]
    for robot in ROBOTS:
        result.append(
            Avatar(
                f"robot:{robot.id}",
                robot.name,
                robot.image,
                robot.id in state.robot_levels,
                f"Открой робота {robot.name}",
            )
        )
    for key, title, unlocked, requirement in (
        ("builder", "Изобретатель", state.jobs_done >= 1, "Заверши первый проект"),
        ("champion", "Страж арены", state.arena_wins >= 5, "Выиграй 5 боёв"),
        ("explorer", "Дружная команда", state.robot_count >= 3, "Собери 3 роботов"),
        ("collector", "Хранитель боксов", state.crates_opened >= 3, "Открой 3 бокса"),
        (
            "master",
            "Мастер света",
            state.craft_counts.get("lamp", 0) >= 5,
            "Собери 5 фонариков",
        ),
    ):
        result.append(
            Avatar(
                f"badge:{key}", title, f"art/avatars/{key}.svg", unlocked, requirement
            )
        )
    if any(
        robot.egg == "cosmic" and robot.id in state.robot_levels for robot in ROBOTS
    ):
        result.append(
            Avatar("egg:cosmic", "Космическое яйцо", "art/egg_cosmic.webp", True)
        )
    return result


def selected_avatar(state):
    return next(
        (
            avatar
            for avatar in avatars(state)
            if avatar.id == state.avatar_id and avatar.unlocked
        ),
        avatars(state)[0],
    )


def refresh_day(state, now, *, before=None):
    day = int(max(0, now) // DAY)
    if day > state.daily_day or not state.daily_base:
        state.daily_day = max(state.daily_day, day)
        state.daily_base = before or {
            spec[2]: getattr(state, spec[2]) for spec in DAILY_SPECS
        }
        state.daily_claimed = []


def daily_goals(state, now):
    current = int(max(0, now) // DAY) <= state.daily_day and bool(state.daily_base)
    rows = []
    for key, title, attribute, target, gold, food, parts in DAILY_SPECS:
        progress = (
            max(0, getattr(state, attribute) - state.daily_base.get(attribute, 0))
            if current
            else 0
        )
        rows.append(
            dict(
                id=key,
                title=title,
                current=min(target, progress),
                target=target,
                gold=gold,
                food=food,
                parts=parts,
                claimed=current and key in state.daily_claimed,
            )
        )
    return rows


def egg_remaining(state, now):
    return (
        max(0, int(state.egg_ready_at - now + 0.999))
        if state.egg_id and state.egg_ready_at
        else 0
    )


def incubation_key(state):
    return f"{state.egg_id}:{state.egg_started_at:.6f}"


def video_offer(state, kind, target="", now=0):
    from gameplay import feeding_target

    if kind == "food":
        return dict(
            title="15 корма", detail="Для кормления команды", kind=kind, target=""
        )
    if kind == "boost" and state.video_boost_end_at <= now:
        return dict(
            title="×2 золото и корм на 2 минуты",
            detail="Только ручные касания; опыт не удваивается",
            kind=kind,
            target="",
        )
    if (
        kind == "training"
        and target in state.robot_levels
        and state.robot_levels[target] < MAX_ROBOT_LEVEL
    ):
        amount = min(
            30,
            max(
                1,
                feeding_target(state.robot_levels[target])
                - state.robot_xp.get(target, 0),
            ),
        )
        return dict(
            title=f"{ROBOT_BY_ID[target].name}: +{amount} опыта",
            detail="До одного уровня за видео",
            kind=kind,
            target=target,
            amount=amount,
        )
    if kind == "incubator" and state.egg_id and egg_remaining(state, now) > 0:
        return dict(
            title="−2 минуты инкубации",
            detail=f"Яйцо: {ROBOT_BY_ID[state.egg_id].name}",
            kind=kind,
            target=incubation_key(state),
        )
    if kind in {"gold", "container", "season_xp"}:
        title = {
            "gold": "50 золота",
            "container": "Контейнер роботов",
            "season_xp": "10 сезонного опыта",
        }[kind]
        return dict(
            title=title,
            detail="Добровольный бонус за завершённое видео",
            kind=kind,
            target="",
        )
    if kind == "order_speed" and state.work_id and state.work_end_at > now:
        return dict(
            title="−30 секунд заказа",
            detail="Ускорение текущего проекта",
            kind=kind,
            target=f"{state.work_id}:{state.work_end_at:.3f}",
        )
    return None


def video_available(state, now):
    count = state.reward_count if int(now // DAY) <= state.reward_day else 0
    remaining = max(0, VIDEO_LIMIT - count)
    cooldown = max(0, int(state.reward_last_at + VIDEO_COOLDOWN - now + 0.999))
    return remaining, cooldown


def grant_video(state, token, offer, now):
    """Called only from the rewarded SDK's earned callback, never an ordinary button."""
    from gameplay import MAX_VALUE, ActionResult, add_robot_xp, feeding_target

    if not token or token in state.reward_tokens:
        return ActionResult(False, "Эта награда уже получена")
    if video_available(state, now)[0] <= 0:
        return ActionResult(False, "Сегодняшние видеобонусы получены")
    kind, target = offer.get("kind"), offer.get("target", "")
    if kind not in {
        "food",
        "boost",
        "training",
        "incubator",
        "gold",
        "container",
        "season_xp",
        "order_speed",
    }:
        return ActionResult(False, "Неизвестная награда")
    if kind == "food":
        state.food = min(MAX_VALUE, state.food + 15)
        message = "+15 корма для команды"
    elif kind == "boost":
        state.video_boost_end_at = max(now, state.video_boost_end_at) + 120
        message = "Двойные золото и корм на 2 минуты"
    elif kind in {"gold", "container", "season_xp", "order_speed"}:
        from collection_progress import grant, add_season_xp

        if kind == "gold":
            state.earn(50, 0)
            message = "+50 золота"
        elif kind == "container":
            grant(state, dict(kind="chests", id="normal", amount=1))
            message = "Получен контейнер роботов"
        elif kind == "season_xp":
            add_season_xp(state, 10, now)
            message = "+10 сезонного опыта"
        else:
            if (
                state.work_id
                and target == f"{state.work_id}:{state.work_end_at:.3f}"
                and state.work_end_at > now
            ):
                state.work_end_at = max(now, state.work_end_at - 30)
                message = "Заказ ускорен на 30 секунд"
            else:
                state.food = min(MAX_VALUE, state.food + 5)
                message = "Проект уже готов: +5 корма"
    elif kind == "training":
        if target not in state.robot_levels:
            return ActionResult(False, "Робот не найден")
        amount = max(1, min(30, int(offer.get("amount", 30))))
        if state.robot_levels[target] < MAX_ROBOT_LEVEL:
            amount = min(
                amount,
                max(
                    1,
                    feeding_target(state.robot_levels[target])
                    - state.robot_xp.get(target, 0),
                ),
            )
            add_robot_xp(state, target, amount)
            message = f"{ROBOT_BY_ID[target].name}: +{amount} опыта"
        else:
            state.food = min(MAX_VALUE, state.food + 15)
            message = "Робот уже вырос полностью: +15 корма"
    else:
        identity = incubation_key(state)
        if identity == target and state.egg_ready_at > now:
            state.egg_ready_at = max(now, state.egg_ready_at - 120)
            message = "Инкубатор ускорен на 2 минуты"
        else:
            state.food = min(MAX_VALUE, state.food + 15)
            message = "Яйцо уже готово: +15 корма вместо ускорения"
    state.reward_tokens = (state.reward_tokens + [token])[-64:]
    day = int(now // DAY)
    if day > state.reward_day:
        state.reward_day, state.reward_count = day, 0
    state.reward_count += 1
    state.reward_last_at = now
    state.modified_at = now
    return ActionResult(True, message)


def perform_extra(state, name, args, now):
    from gameplay import MAX_VALUE, ActionResult

    if name == "_video_reward":
        return grant_video(state, args[0], args[1], now)

    if name == "avatar":
        choice = next(
            (item for item in avatars(state) if item.id == args[0] and item.unlocked),
            None,
        )
        if choice is None:
            return ActionResult(False, "Сначала открой эту иконку")
        state.avatar_id = choice.id
        state.modified_at = now
        return ActionResult(True, "Иконка профиля выбрана")
    if name == "daily":
        goal = next(
            (item for item in daily_goals(state, now) if item["id"] == args[0]), None
        )
        if not goal or goal["claimed"] or goal["current"] < goal["target"]:
            return ActionResult(False, "Сначала выполни цель дня")
        state.daily_claimed.append(goal["id"])
        state.dailies_done += 1
        state.earn(goal["gold"], 5)
        state.food = min(MAX_VALUE, state.food + goal["food"])
        state.parts = min(MAX_VALUE, state.parts + goal["parts"])
        state.modified_at = now
        return ActionResult(
            True,
            f"Цель дня: +{goal['gold']} золота, +{goal['food']} корма, +{goal['parts']} деталей",
        )
    if name == "crate":
        kind = args[0]
        cost = 8 if kind == "supply" else 20
        target = args[1] if len(args) > 1 else ""
        if kind not in {"supply", "egg"} or state.parts < cost:
            return ActionResult(False, "Не хватает деталей для бокса")
        if kind == "egg":
            robot = ROBOT_BY_ID.get(target)
            if (
                not robot
                or robot.level > state.level
                or target in state.robot_levels
                or target == state.egg_id
                or state.egg_stock.get(target)
            ):
                return ActionResult(
                    False, "Выбери доступное яйцо, которого ещё нет в команде"
                )
        state.parts -= cost
        state.crates_opened += 1
        if kind == "supply":
            state.earn(50, 0)
            state.food = min(MAX_VALUE, state.food + 15)
            message = "Бокс припасов: +50 золота и +15 корма"
        else:
            state.egg_stock[target] = 1
            message = (
                f"Яйцо {ROBOT_BY_ID[target].name} в хранилище — помести его в инкубатор"
            )
        state.modified_at = now
        return ActionResult(True, message)
    if name == "stock_egg":
        identity = args[0]
        robot = ROBOT_BY_ID.get(identity)
        if (
            not robot
            or not state.egg_stock.get(identity)
            or identity in state.robot_levels
            or state.egg_id
        ):
            return ActionResult(False, "Сначала освободи инкубатор")
        state.egg_stock.pop(identity)
        state.egg_id = identity
        state.egg_started_taps = state.manual_taps
        state.egg_started_at = now
        state.egg_ready_at = now + max(30, robot.hatch_seconds)
        state.modified_at = now
        return ActionResult(
            True, f"{robot.name}: инкубация началась. Касания ускоряют таймер"
        )
    if name == "lamp_toggle":
        if not state.craft_counts.get("lamp"):
            return ActionResult(False, "Сначала собери фонарик")
        state.lamp_on = not state.lamp_on
        state.modified_at = now
        return ActionResult(
            True, "Фонарик включён" if state.lamp_on else "Фонарик выключен"
        )
    if name == "tutorial_done":
        state.tutorial_seen = True
        return ActionResult(True)
    return None
