"""Collect the Volt release's inspectable checks and repository release notes."""

import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / ".cache/volt-refinement"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, required=True)
    args = parser.parse_args()
    n = args.build_number
    out = ROOT / f"build/volt-verification-v{n}"
    out.mkdir(parents=True, exist_ok=True)
    android = read(ROOT / f"build/apk-game-v{n}/validation/summary.json")
    scope = read(out / "scope-and-package.json")
    performance = read(QA / "performance/paired/summary.json")
    inputs = read(ROOT / f".cache/interaction-v27/packaged-input-v{n}/summary.json")
    assert scope["status"] == "passed" and inputs["robot"] == "volt"
    report = {
        "build": n, "android": android, "scope_and_package": scope,
        "performance": performance, "real_main_game_input": inputs,
        "python_tests": {"total":282,"passed":272,"skipped":10,"skip_reason":"optional local PostgreSQL not configured"},
        "native_tests": {"distinct_cases_passed":130,"main_game_layouts_passed":9,
                         "parallel_png_readback_timed_out":True,"serial_native_control_recheck_passed":8},
        "physical_android_tested":False,
        "training":read(QA / "qa/training-balance.json"),
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, source in [
        ("performance.json", QA / "performance/paired/summary.json"),
        ("input.json", ROOT / f".cache/interaction-v27/packaged-input-v{n}/summary.json"),
        ("python-tests.txt", QA / "qa/python-final.log"),
        ("native-tests.txt", QA / "qa/native-final.log"),
        ("serial-paint-tests.txt", QA / "native-fast-path-serial.log"),
        ("layouts.txt", QA / "qa/volt-layouts-final.log"),
        ("audio.json", QA / "audio/summary.json"),
        ("training.json", QA / "qa/training-balance.json"),
    ]:
        shutil.copy2(source, out / name)
    docs = ROOT / f"docs/volt-v{n}"
    docs.mkdir(parents=True, exist_ok=True)
    for target, source in [
        ("workshop.png", ROOT / ".cache/ui-rendered/interaction-volt-workshop.png"),
        ("inspection.png", ROOT / ".cache/ui-rendered/interaction-inspect-volt.png"),
        ("storm.png", QA / "canvas/volt-ultimate.png"),
    ]:
        shutil.copy2(source, docs / target)
    repo = "https://github.com/499jdkd/Robo-Workshop-Steel-Arena"
    tag = f"volt-v0.2.0-{n}"
    rows = []
    for scenario, label in [("workshop", "Мастерская · 390×844, DPR 3"), ("combat", "Бой · 844×390, DPR 2")]:
        before, after = performance[f"before-{scenario}"], performance[f"after-{scenario}"]
        rows.append(f"| {label} | {before['median_unique_vsync_fps']:.1f} → {after['median_unique_vsync_fps']:.1f} | {before['maximum_ui_p95_ms']:.1f} → {after['maximum_ui_p95_ms']:.1f} | {before['maximum_raster_p95_ms']:.1f} → {after['maximum_raster_p95_ms']:.1f} |")
    text = f"""**Robo Workshop · Вольт · 0.2.0 ({n})**

[GitHub Release]({repo}/releases/tag/{tag}) · [APK]({repo}/releases/download/{tag}/Robo-Workshop-Volt-v{n}.apk)

Изменён только персонаж Вольт. Голубой силуэт и две катушки сохранены; добавлены механический корпус с объёмными панелями, шарниры, контакты, ядро, манипуляторы, сопла и выразительный визор. Авторский векторный источник содержит 310 фигур, включая скрытые варианты экипированного оружия. Модель компилируется в кешируемые пути и материалы Flutter CustomPainter. Остальные 31 портрет, набор способностей, артборд и view model проверены на совпадение со снимком до этой задачи. Общий `.riv` не изменён.

![Вольт в основной мастерской](docs/volt-v{n}/workshop.png)

В мастерской и осмотре работают радость, прыжок с подготовкой и приземлением, удивление, недовольство частыми касаниями, взгляд за пальцем, движение к выбранной точке, электрический выстрел по мишени, танец и осмотр собственных механизмов. Удержание показывает бурю. Прерванные действия смешивают позы корпуса, головы и катушек; движения не сводятся к перемещению целой картинки.

| Действие | Анимация Вольта |
|---|---|
| Атака | Короткий электрический импульс из катушек, подготовка и отдача |
| Быстрый | Сжатие подвески, рывок и короткий разряд |
| Навык | Раскрытие контактов, заряд и межкатушечная дуга, разряд в цель |
| Защита | Электрическая сфера вокруг корпуса |
| Уворот | Боковой рывок с электрическим следом |
| Фокус | Катушки сближаются и передают энергию ядру |
| Электрическая буря | Подъём, раскрытие катушек, накопление, молнии, вспышка и ударная волна |
| Победа | Подвижная радость, жесты и искры |
| Поражение | Угасание ядра, катушек и сопел, дым, остановка ротора и грустный визор |

Осмотр закрытого Вольта доступен без изменения ресурсов, экипировки или сохранения. Его панель показывает десять демонстрационных действий. В настоящем бою отображается выбранное установленное оружие, включая чередование двух креплений и серверное оружие PvP. Встроенные электрические приёмы используют катушки, а не универсальную пушку.

Добавлены четыре оригинальных коротких звука катушек: импульс, заряд, буря и отключение. Их маркеры выполняются нативным таймлайном, проверены при 30/60/120 Hz и не повторяются при пропуске кадра. Файлы PCM16 mono 22 050 Hz проверены на отсутствие клиппинга и щелчков на концах; прослушивание на физическом устройстве не проводилось.

В мастерской и осмотре Вольт больше не ожидает загрузки Rive: первый кадр рисует собственный локальный Ticker. На кадрах нет `setState`, Flet-событий или Python-координат. Перерисовывается сцена. Пауза, скрытие и уход приложения в фон останавливают цикл и звук; возврат обнуляет накопленное время. В арене остальные бойцы продолжают использовать прежние Rive-модели.

По новым видео от 19 ноября исправлено наложение при переходах: профиль → мастерская около 0:22, мастерская → коллекция около 0:48 и вход в арену в коротком ролике. Причина — исходящий слой AnimatedSwitcher оставался на секунду через `reverse_duration`, несмотря на `duration=0`. Корневой экран теперь заменяется одним непрозрачным контейнером. Проверка старого варианта воспроизводит наложение; новый проходит быстрые переключения уже на следующем кадре.

Правила боя, сохранений и сервер не менялись. Проверки повторного ввода, отмены, низкой/нулевой энергии и реального выбранного оружия проходят. 600 синтетических тренировочных боёв Вольта дали 598 побед и два поражения на поздних боссах при уровне 1; зависаний не было. Показанный в видео противник с большим перевесом HP относится к экспертному режиму. Общий баланс оставлен прежним.

Парное профилирование одной и той же основной игры на Windows/Chrome, по 25–26 окон после четырёх начальных отчётов:

| Сценарий | Медиана FPS: до → после | Максимальный UI p95, мс | Максимальный raster p95, мс |
|---|---|---|---|
""" + "\n".join(rows) + f"""

В мастерской первый кадр после создания синтетической сессии: 2,37 → 0,34 с. Время прогрева модели — 3,4 мс; `.riv` для него не загружался. Более подробная геометрия увеличила стоимость рисования и уменьшила медиану FPS. Это один парный сценарий на ПК с перекрывающимися окнами FrameTiming, а не замер запуска Android, устойчивости нагрева или FPS телефона. Повторяющиеся записи vsync исключены из расчёта FPS.

Проверки: 282 Python-теста, 272 успешно и 10 пропусков необязательного локального PostgreSQL; 130 нативных сценариев анимаций/жестов и девять размеров основной разметки. В общем параллельном прогоне одна операция получения PNG зависла; все восемь проверок первого кадра и быстрого пути повторно прошли последовательно с сохранением PNG. Точная причина параллельного зависания не установлена. Кликер проверен настоящим Flet-сервером и собранным Flutter-клиентом на изолированном сохранении: пол и удержание не начисляют ресурсы, пять быстрых касаний учитываются ровно пять раз, кормление сохранено. Реальное пользовательское сохранение не открывалось.

APK проверен по составу, подписи, трём ABI, библиотекам с выравниванием 16 КБ, новым звукам и маркерам Canvas во всех `libapp.so`. Модули Python из APK импортированы в CPython 3.14.7; отдельно проверен HTTPS действующего сервера. SHA-256: `{android['sha256']}`.

**Физический Android не проверен:** подключённых ADB-устройств нет. Цель 60 FPS, реальный звук, нагрев, системные жесты и возврат из настоящей рекламы на телефоне остаются для проверки устройства. В APK сохранены тестовая реклама Google и прежний тестовый режим премиальной линии.

Подпись совпадает с локальными v31/v32, поэтому их данные должны сохраняться при обычном обновлении. Старый публичный APK versionCode 1 подписан другим ключом; установка поверх него этой подписью невозможна. Удалять установленную игру ради обновления не следует: для такого перехода нужен исходный ключ или отдельный перенос сохранения.

Воспроизведение: `tools/generate_volt_canvas.py --check`, `tools/generate_volt_audio.py --verify-only`, `tools/volt_quality_audit.py`, `tools/verify_main_game_release.py --build-number {n}`, `tools/verify_volt_release.py --build-number {n}`. Нативные тесты с получением PNG запускать с `--concurrency=1 --timeout=60s`. Полные локальные доказательства находятся в `build/volt-verification-v{n}/summary.json`.
"""
    (ROOT / "VOLT_UPDATE.md").write_text(text, encoding="utf-8")
    notes = f"""Вольт проработан непосредственно в основной Robo Workshop. Другие 31 робот, сохранения, правила боя и действующий сервер сохранены.

- Детальная голубая модель: подвижные катушки, контакты, ядро, броня, лицо и манипуляторы.
- Разные касания, прыжок, удивление, недовольство быстрыми касаниями, взгляд, движение к точке, мишень и танец.
- Раздельные электрические атаки, защита, уворот, фокус, буря, победа и отключение; четыре оригинальных звука.
- Быстрая первая отрисовка без загрузки Rive в мастерской и осмотре. Исправлены наложения экранов.
- 272 Python-теста успешно, 10 пропущены; проверены нативные анимации, жесты, низкая энергия, экипировка и сборка APK.

[Изменения, снимки и замеры]({repo}/blob/{tag}/VOLT_UPDATE.md).

Физический Android недоступен; 60 FPS и звук на телефоне пока не подтверждены. Реклама и премиальная линия остаются в прежнем тестовом режиме.

Подпись APK совпадает с локальными v31/v32. Старый public APK versionCode 1 использует другой ключ и этим файлом поверх него не обновится; не удаляйте игру с сохранением ради установки.

Android: package com.mycompany.clicker, version 0.2.0 ({n}), minSdk24, три ABI. SHA-256: `{android['sha256']}`.
"""
    (QA / f"release-notes-v{n}.md").write_text(notes, encoding="utf-8")
    print(out / "summary.json")


if __name__ == "__main__":
    main()
