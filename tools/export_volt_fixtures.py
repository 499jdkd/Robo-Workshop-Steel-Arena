"""Main-game Volt layouts at narrow portrait, portrait and landscape sizes."""

import asyncio
from export_ui_fixtures import fixture


async def main():
    for width, height, suffix in [(320, 640, "-small"), (390, 844, ""), (844, 390, "-landscape")]:
        await fixture("interaction-volt-workshop" + suffix, 0, width, height, robot_id="volt")
        await fixture("interaction-inspect-volt" + suffix, 1, width, height, robot_id="volt")
        await fixture("interaction-volt-energy" + suffix, 2, width, height, battle=True, robot_id="volt", energy=1)
    print("Exported nine main-game Volt layouts")


if __name__ == "__main__":
    asyncio.run(main())
