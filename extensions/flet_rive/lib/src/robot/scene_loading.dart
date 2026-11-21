import 'dart:math' as math;
import 'package:material_ui/material_ui.dart';

/// Immediate Flutter placeholder while the single shared Rive file decodes.
class SceneLoadingRobot extends StatefulWidget {
  const SceneLoadingRobot({super.key});
  @override
  State<SceneLoadingRobot> createState() => _SceneLoadingRobotState();
}

class _SceneLoadingRobotState extends State<SceneLoadingRobot>
    with SingleTickerProviderStateMixin {
  late final controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat();
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Center(child: Semantics(label: 'Робот готовится к работе',
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedBuilder(animation: controller, builder: (_, child) => Transform.translate(
        offset: Offset(0, MediaQuery.disableAnimationsOf(context) ? 0 : -6 * math.sin(controller.value * math.pi * 2)),
        child: child), child: const Icon(Icons.smart_toy_rounded, size: 68, color: Color(0xFF8CE7FF))),
      const SizedBox(height: 12),
      const Text('Робот готовится к работе…', style: TextStyle(fontSize: 12, color: Color(0xFFCEEBF7))),
    ])));
}
