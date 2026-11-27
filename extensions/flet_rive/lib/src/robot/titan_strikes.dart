import 'dart:math' as math;
import 'package:material_ui/material_ui.dart';
import 'game_motion.dart';
import 'titan_motion.dart';
import 'volt_motion.dart' show VoltFrame;

class TitanFistStrike {
  const TitanFistStrike({
    required this.left,
    required this.detached,
    required this.socket,
    required this.tip,
    required this.rotation,
    required this.impact,
    required this.thrust,
  });
  final bool left, detached;
  final Offset socket, tip;
  final double rotation, impact, thrust;
}

Offset _curve(Offset a, Offset b, double u, double lift) =>
    Offset.lerp(a, b, u)! + Offset(0, -4 * u * (1 - u) * lift);

/// All endpoints come from the live actor and live defender, in scene pixels.
/// Normal/quick fists stay on telescoping shafts; only the skill disconnects.
List<TitanFistStrike> titanFistStrikes(
  VoltFrame frame,
  GamePose pose,
  Offset origin,
  Offset target,
  double scale,
  double facing,
) {
  final t = frame.t, result = <TitanFistStrike>[];
  for (final left in [true, false]) {
    if ((pose.extra[left ? 'titanExternalFistL' : 'titanExternalFistR'] ?? 0) <
        .5)
      continue;
    final socket = titanWrist(pose, origin, scale, facing, left);
    final rest = titanFist(pose, origin, scale, facing, left);
    final detached = frame.action == 'special';
    final reach = titanPunchReach(frame.action, t, left);
    Offset tip;
    double rotationWeight;
    if (detached) {
      if (t <= titanSkillImpact) {
        final u = smooth(
          (t - titanSkillRelease) / (titanSkillImpact - titanSkillRelease),
        );
        tip = _curve(rest, target, u, 42 * scale);
        rotationWeight = 1;
      } else {
        final u = smooth((t - .81) / .19);
        tip = _curve(target, rest, u, -25 * scale);
        rotationWeight = 1 - smooth((t - .92) / .08);
      }
    } else {
      tip = Offset.lerp(rest, target, reach)!;
      rotationWeight = reach;
    }
    final armRotation =
        pose.rotation +
        (left ? pose.armL + pose.foreL : pose.armR + pose.foreR);
    final delta = target - socket;
    final aim = math.atan2(delta.dy, delta.dx * facing) - math.pi / 2;
    final turn = (aim - armRotation + math.pi) % (2 * math.pi) - math.pi;
    result.add(
      TitanFistStrike(
        left: left,
        detached: detached,
        socket: socket,
        tip: tip,
        rotation: armRotation + turn * rotationWeight,
        impact: titanPunchImpact(frame.action, t, left),
        thrust: detached && t < titanSkillImpact ? 1 : 0,
      ),
    );
  }
  return result;
}

/// Cross the defender exactly at the damage boundary, then keep moving beyond
/// the visible arena. Velocity stays continuous at contact, including close foes.
Offset titanWaveFront(
  Offset ground,
  Offset target,
  double floor,
  double scale,
  double t, {
  double facing = 1,
  Rect? viewport,
}) {
  final dx = target.dx - ground.dx;
  final direction = dx.abs() < .001 ? facing.sign : dx.sign;
  if (t <= .9) {
    return Offset(
      ground.dx + dx * unit((t - titanQuakeRelease) / (.9 - titanQuakeRelease)),
      floor - 2 * scale,
    );
  }
  final speed = dx.abs() / (.9 - titanQuakeRelease);
  final edge = viewport == null
      ? target.dx + direction * math.max(160 * scale, dx.abs() * .5)
      : (direction > 0
            ? viewport.right + 70 * scale
            : viewport.left - 70 * scale);
  final beyond = math.max(
    speed * .1,
    math.max(100 * scale, (edge - target.dx) * direction),
  );
  final elapsed = (t - .9).clamp(0.0, .1);
  final distance =
      speed * elapsed + (beyond - speed * .1) * math.pow(elapsed / .1, 2);
  return Offset(target.dx + direction * distance, floor - 2 * scale);
}
