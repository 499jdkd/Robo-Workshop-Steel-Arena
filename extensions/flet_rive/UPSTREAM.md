The standard Rive control is copied from the MIT-licensed Flet v1.0.4 tree:
https://github.com/flet-dev/flet/tree/v1.0.4/sdk/python/packages/flet-rive/src/flutter/flet_rive

`lib/src/robot/` and `lib/src/robot_scene.dart` add an isolated robot lab control.
They do not change the ordinary Rive control or any game rules.
The Rive runtime is pinned to 0.14.11, within upstream's ^0.14.0 range.
This extension is referenced only by prototypes/rive_robot, not the game build.
