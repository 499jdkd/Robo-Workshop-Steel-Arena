"""Cosmetic-only selections; they never enter the combat stat budget."""

SKINS = {
    f"steel-{n}": name
    for n, name in enumerate(
        (
            "Лазурная сталь",
            "Северное сияние",
            "Золотой сплав",
            "Лесной металл",
            "Розовый кварц",
            "Белый титан",
        )
    )
}
SKIN_COLORS = ("#65D4FF", "#A8AFF0", "#E8C77E", "#8CE3BC", "#F29CCB", "#E6F1FF")


def skin_price(identity):
    return (500, 900, 1400, 2200, 3200, 5000)[list(SKINS).index(identity)]


EMOTIONS = {
    "salute": ("Приветствие", "joy"),
    "dance": ("Танец победы", "victory"),
    "curiosity": ("Любопытство", "surprise"),
    "determination": ("Решительность", "anger"),
    "bashful": ("Смущение", "fear"),
    "celebration": ("Праздник", "feed"),
}


def animation_name(identity):
    return EMOTIONS.get(
        identity, list(EMOTIONS.values())[sum(map(ord, identity)) % len(EMOTIONS)]
    )


def cosmetic_name(kind, identity):
    if kind == "skin":
        return SKINS.get(identity, identity)
    if kind == "animation":
        return animation_name(identity)[0]
    return "Стальная эмблема " + identity.removeprefix("season-")
