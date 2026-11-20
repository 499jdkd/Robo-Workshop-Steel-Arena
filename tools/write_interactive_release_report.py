"""Collect public release checks and visual evidence, without player data."""

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from robot_abilities import ABILITIES
from robot_designs import DESIGNS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, required=True)
    args = parser.parse_args()
    n = args.build_number
    qa = ROOT / ".cache/interaction-v27"
    out = ROOT / f"build/game-verification-v{n}"
    out.mkdir(parents=True, exist_ok=True)
    windows = json.loads((ROOT / f"build/windows-motion-v{n}/validation/summary.json").read_text(encoding="utf-8"))
    android = json.loads((ROOT / f"build/apk-game-v{n}/validation/summary.json").read_text(encoding="utf-8"))
    inputs = json.loads((qa / f"packaged-input-v{n}/summary.json").read_text(encoding="utf-8"))
    public = json.loads((qa / "public-arena.json").read_text(encoding="utf-8"))
    native_paints = [json.loads(line) for line in (qa / f"windows-v{n}-selftest.scenes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(scene.get("renderer") == "rive" and scene.get("robot") for scene in native_paints)
    workshop_profile = ROOT / ".cache/rework-review/interaction-v27-current-startup/performance-summary.json"
    combat_profile = ROOT / ".cache/rework-review/interaction-v31-combat-final/performance-summary.json"
    performance = {
        "workshop": json.loads(workshop_profile.read_text(encoding="utf-8")),
        "combat": json.loads(combat_profile.read_text(encoding="utf-8")),
        "limitations": [
            "Desktop headless Chrome profile; no physical Android device tested.",
            "Combat console telemetry yielded only eight rolling samples after warmup; this is a small sample, not a sustained phone performance result.",
            "Startup comparison is one run per revision, measured from synthetic session creation, not OS process launch.",
        ],
        "startup": {},
    }
    for name, directory in [("before", "baseline-startup-2"), ("after", "current-startup")]:
        first_render = json.loads((qa / directory / "first-render.json").read_text(encoding="utf-8"))
        first_paint = json.loads((qa / directory / "first-paint.jsonl").read_text(encoding="utf-8").splitlines()[0])
        performance["startup"][name] = {**first_render, "first_native_paint": first_paint}
    (out / "performance.json").write_text(json.dumps(performance, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, source in [
        ("windows.json", ROOT / f"build/windows-motion-v{n}/validation/summary.json"),
        ("android.json", ROOT / f"build/apk-game-v{n}/validation/summary.json"),
        ("public-arena.json", qa / "public-arena.json"),
        ("packaged-input.json", qa / f"packaged-input-v{n}/summary.json"),
        ("workshop.png", qa / f"packaged-input-v{n}/after.png"),
        ("mobile-energy.png", ROOT / ".cache/ui-rendered/interaction-energy-small.png"),
        ("rewards.png", ROOT / ".cache/ui-rendered/interaction-factory-rewards.png"),
        ("workshop-performance.json", workshop_profile),
        ("combat-performance.json", combat_profile),
        ("windows-first-paint.jsonl", qa / f"windows-v{n}-selftest.scenes.jsonl"),
        ("apk-python-imports.txt", ROOT / f"build/apk-game-v{n}/validation/python-imports.txt"),
        ("python-regressions.txt", qa / "python-regressions-final.log"),
        ("python-final-focused.txt", qa / "python-final-focused.log"),
        ("native-scenes-and-input.txt", qa / "native-final-input.log"),
        ("native-compact-tabs.txt", qa / "native-arena-tabs.log"),
    ]:
        shutil.copy2(source, out / name)
    report = {
        "build": n, "main_game": True, "python_tests": {"total":261,"passed":251,"skipped":10,"skip_reason":"optional local PostgreSQL not configured"},
        "native_checks": {"layouts":164,"skill_and_super_scenes":65,"motion_and_gestures":12,"affected_layout_rechecks":39,"system_inset_rechecks":4,"cost_icon_rechecks":2,"compact_arena_tabs":2},
        "windows":windows,"android":android,"real_packaged_input":inputs,"public_pvp":public,
        "windows_webview": {"real_native_paint": native_paints, "automatic_png_capture_completed": False, "capture_test_stopped_after_seconds":40},
        "performance":performance,
        "physical_android_tested":False,
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for identity, ability in ABILITIES.items():
        rows.append(f"| {DESIGNS[identity]['name']} | {ability.title} | {ability.choreography}. {ability.effect}. |")
    text = f"""**Robo Workshop — обновление интерактивности, сборка {n}**

Изменения внесены в основную игру. Идентификаторы роботов, коллекция, сохранения, экипировка, кормление, кликер, сезон и действующий PvP сохранены. Приложенное видео от 18 ноября просмотрено, включая участок 1:35–1:50 с 1/12 энергии и полным суперзарядом.

Готовые пакеты: [Windows ZIP](build/windows-motion-v{n}/Clicker-Windows.zip), [Android APK](build/apk-game-v{n}/clicker.apk). В архиве Windows нужно запустить `Clicker/Clicker.exe`. Запуск из исходников: `run_game.cmd` или `run_game_windows.cmd`.

Навигация получила постоянно видимые подписи, иконки 28 dp и высоту 80 dp. Каждая из четырёх областей больше 48×48 dp даже при ширине 320. Между рекламой и меню добавлен отдельный отступ; системная нижняя область учитывается также в раскрытых сценах. Карточки коллекции стали крупнее и показывают по два робота на узком экране. У контейнеров пять разных конструкций, отдельные значки и экран полученных наград. Изображения магазина и сезонных наград увеличены.

В мастерской касание персонажа сохраняет кликер и кормление, но выбирает разные реакции с учётом характера. Быстрые касания, удержание, движение к точке, взгляд за пальцем и самостоятельные действия обрабатываются нативно. В осмотре любого, в том числе закрытого робота, доступны атака, навык, супер, защита и масштабирование. Осмотр не меняет ресурсы, сохранение или экипировку.

Стоимость и доступность боевых действий вычисляются общими правилами для интерфейса и выполнения хода. При 1/12 энергии супер с зарядом 100% недоступен с объяснением; бесплатные щит и фокус остаются доступны и видны первыми. Показываются энергия, фокус, нагрев и суперзаряд отдельно, восстановление, примерный урон, перезарядка и причины блокировки. Подробности по удержанию объясняют требования и контрприёмы. Есть короткое обучение с выбором ответов, скорость ×1/×1,5/×2 и уменьшение эффектов. Оборванная анимация освобождает ввод; повторные команды не создают дополнительные ходы. Экипированное оружие и чередующиеся крепления используются в бою.

В тренировке характеристики противника ограничены относительно бойца игрока. Сложные и экспертные боты учитывают подготовку, щит, уворот и свои ресурсы; эксперт применяет навыки. Обычная атака, быстрый удар, навык и супер имеют разные постановки. Супер использует полное движение корпуса и конечностей, собственный эффект, звук и короткое изменение камеры; навык — более короткий отдельный контрприём.

Загрузка больше не создаёт 24 аудиоплеера заранее и не создаёт невидимого противника в мастерской. Rive-файл 850 270 байт разделяется кешем; экземпляры создаются только для видимых бойцов. Звуки загружаются при использовании, невидимые сцены останавливаются, количество частиц ограничено. Тяжёлые экраны импортируются при открытии, заставка Rive показывает анимированного робота. Локальный интерфейс не ожидает сетевого подключения.

В одном замере Windows/Chrome с одинаковым размером 390×844 и DPR 3 первая отрисовка робота после создания синтетической игровой сессии изменилась примерно с 3,78 до 1,78 с, Python-построение первого интерфейса — со 137 до 111 мс. Это один сценарий на ПК, а не универсальный процент ускорения или измерение запуска Android. В профиле мастерской получено 30 окон FrameTiming после прогрева; максимальный UI p95 — 7,5 мс, raster p95 — 2,5 мс. Бой дал только восемь окон после прогрева: UI p95 до 6,8 мс и raster p95 до 2,9 мс; малая выборка не доказывает длительную стабильность. [Замеры и ограничения](build/game-verification-v{n}/performance.json).

Проверки: 261 Python-тест, 251 успешно, 10 пропусков из-за отсутствующей конфигурации локального PostgreSQL. Нативные проверки охватывают 164 разметки, 65 сцен навыков/суперприёмов и 12 проверок движения/жестов. После правок повторены затронутые экраны, в том числе 320×640, 390×844, 844×390 и нижняя системная область 24 dp. Все 32 навыка и 32 суперприёма отрисованы настоящими Rive-моделями; это проверки общих игровых компонентов.

В самом Windows-пакете проверен реальный путь Flet → GameRive → Python → сохранение: пол и удержание не начисляют ресурсы, пять быстрых касаний записывают ровно пять действий и 20 монет; кормление сохранено. Данные использовались только синтетические. WebView2 также сообщил о реальной первой отрисовке Rive; автоматическое получение PNG через WebView2 не завершилось, поэтому визуальная проверка последнего пакета и ввод выполнены его упакованным клиентом через Chrome. Проверка снимка остановлена через 40 с. [Снимок мастерской](build/game-verification-v{n}/workshop.png).

Два отдельных тестовых клиента завершили дружеский бой на существующем Render/Neon-сервере за {public['turns']} ходов. Проверены одинаковые состояния, повтор команды, повторный вход, друзья, история и клановые роли. Локальный прогресс и рейтинговые награды не изменились; публичный подбор соперников не использовался. [Отчёт PvP](build/game-verification-v{n}/public-arena.json).

Windows: сверены {len(windows['verified_modules'])} Python-модуля и {windows['verified_assets']} ресурсов, пакетный клиент, Rive WASM и шрифты. Используется основной Python/Flet-клиент с WebView2, как в предыдущих сборках. APK: versionCode {n}, package ID `com.mycompany.clicker`, minSdk 24, targetSdk 36, три ABI, 48 модулей и 24 звука; 128 библиотек проверены на выравнивание 16 КБ. Импорт 18 модулей из APK выполнен CPython 3.14.7, отдельно проверен HTTPS к серверу. Подпись совпадает с прежними тестовыми APK.

**Физический Android не проверен:** ADB-устройств нет. FPS, нагрев, реальные повороты, системные жесты, звук и возврат после настоящей рекламы на телефоне требуют проверки на устройстве. Размеры Android в widget-тестах не являются таким тестом. В APK тестовая реклама Google и прежний тестовый режим премиальной линии; production Billing не добавлялся.

| Пакет | SHA-256 |
|---|---|
| Windows ZIP | `{windows['sha256']}` |
| Android APK | `{android['sha256']}` |

Боевые идентичности существующих роботов:

| Робот | Суперприём | Постановка и эффект |
|---|---|---|
""" + "\n".join(rows) + "\n"
    (ROOT / "INTERACTIVE_UPDATE.md").write_text(text, encoding="utf-8")
    print(out / "summary.json")


if __name__ == "__main__":
    main()
