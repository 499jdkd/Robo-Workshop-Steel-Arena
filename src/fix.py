import re

files = ["c:/Clicker/src/main_screen.py", "c:/Clicker/src/shop_screen.py"]
vars_to_replace = [
    "level",
    "session_taps",
    "coin",
    "coins_in_level",
    "base_auto_click_power",
    "auto_click_power",
    "auto_click_price",
    "offline_income_power",
    "offline_income_price",
    "current_screen",
    "boost_time_left",
    "boost_multiplier",
    "click_power",
    "base_click_power",
    "double_click_price",
    "double_click_level",
    "boost_level",
    "boost_price",
    "boost_duration",
]

for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace("from config import *", "import config")
    content = re.sub(r"^[ \t]*global .*\n", "", content, flags=re.MULTILINE)

    for var in vars_to_replace:
        content = re.sub(
            r"(?<!\.)\b" + var + r"\b(?![\'\"\]])", f"config.{var}", content
        )

    for var in vars_to_replace:
        content = content.replace(f"['config.{var}']", f"['{var}']")
        content = content.replace(f'["config.{var}"]', f'["{var}"]')
        content = content.replace(f"config.config.{var}", f"config.{var}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
