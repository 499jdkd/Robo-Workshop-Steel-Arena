import 'package:flet/flet.dart';
import 'package:flutter/cupertino.dart';

import 'rive.dart';
import 'robot_scene.dart';
import 'game_scene.dart';
import 'game_countdown.dart';
import 'game_factory.dart';

class Extension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "GameFactory":
        return GameFactoryControl(key: key, control: control);
      case "GameCountdown":
        return GameCountdown(key: key, control: control);
      case "GameRive":
        return GameRiveControl(key: key, control: control);
      case "Rive":
        return RiveControl(control: control);
      case "RobotRive":
        return RobotRiveControl(key: key, control: control);
      default:
        return null;
    }
  }

  @override
  void ensureInitialized() {
    // Rive controls initialise their own renderer when first shown. Volt's
    // native vector control, factory and countdown need no Rive runtime.
  }
}
