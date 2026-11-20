# Игровые ресурсы

## Мастерская

`src/assets/art/workshop-future-v1.png` — фон, созданный через OpenAI ImageGen
для этой игры, режим generation. Это фон без персонажа; робот рисуется отдельно
из Rive и не является частью растровой картинки.

Исходный результат: `C:/Users/dell/.codex/generated_images/01a1d5a8-55c1-73e3-8b8a-783764745c21/exec-5d5c163d-d5b4-4cf5-a953-1213e820a75e.png`.

Prompt:

> Use case: stylized-concept. Asset type: production background for the existing mobile robot collection game Robo Workshop, not a UI mockup. Create one polished futuristic robot workshop environment with a large EMPTY circular maintenance platform centered in the lower middle, eye-level three-quarter frontal view. Navy blue and steel blue metal architecture, cyan neon rails and softly glowing platform, warm amber workbench lighting, articulated repair arms and small fans on left/right edges, mechanical gears, tool cabinets and a large bright window showing a distant friendly futuristic city. Premium stylized 3D mobile game render, richly shaded rounded metal surfaces, crisp clear silhouettes, beautiful atmospheric lighting like a collectible robot adventure. Spacious clear central area reserved for an independently animated robot; no robot or character, no text, no numbers, no buttons, no icons, no HUD, no watermark. Horizontal 3:2 composition, platform floor at roughly 82 percent down the image. Balance readable dark backdrop with luminous cyan accents and small amber highlights.

## Роботы и экипировка

Редактируемые векторные модели, портреты и иконки созданы генераторами проекта:
`animation/rive/generate_collection_rigs.py`, `animation/rive/weapon_parts.py`,
`tools/generate_game_icons.py`. Runtime-asset публикуется официальным Rive CLI;
заставка бесплатного плана сохраняется. Исходники RML хранятся в Git вместе с
готовым `.riv`, необходимым приложению.

24 коротких PCM-эффекта синтезируются `tools/prepare_game_animation.py`; это
собственные звуки проекта, а не извлечённые эффекты сторонней игры.
