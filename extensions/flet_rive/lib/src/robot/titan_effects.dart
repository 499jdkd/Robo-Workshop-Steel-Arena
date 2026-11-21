import 'dart:math' as math;
import 'package:material_ui/material_ui.dart';
import 'game_motion.dart';
import 'volt_motion.dart' show VoltFrame;
import 'titan_motion.dart';

/// Mechanical armor and seismic terrain. All loops have a small fixed budget;
/// no blur, saveLayer, asynchronous particles or Python frame messages.
void paintTitanEffects(
  Canvas c,
  VoltFrame frame,
  GamePose pose,
  Offset origin,
  Offset target,
  double floor,
  double s, {
  double facing = 1,
  bool reduced = false,
}) {
  final t = frame.t,
      heavy = frame.action == 'ultimate',
      skill = frame.action == 'special';
  const gold = Color(0xFFFFCB60),
      white = Color(0xFFFFF2CD),
      dark = Color(0xFF17242E),
      steel = Color(0xFFB5C2BE);
  final paint = Paint()
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round;
  void path(Path p, Color color, double alpha, {double width = 0}) {
    c.drawPath(
      p,
      paint
        ..color = color.withValues(alpha: unit(alpha))
        ..style = width == 0 ? PaintingStyle.fill : PaintingStyle.stroke
        ..strokeWidth = math.max(.65, width * s),
    );
  }

  void line(Offset a, Offset b, Color color, double alpha, double width) {
    path(
      Path()
        ..moveTo(a.dx, a.dy)
        ..lineTo(b.dx, b.dy),
      color,
      alpha,
      width: width,
    );
  }

  void oval(
    Offset center,
    double rx,
    double ry,
    Color color,
    double alpha, {
    double width = 0,
  }) {
    c.drawOval(
      Rect.fromCenter(center: center, width: rx * 2 * s, height: ry * 2 * s),
      paint
        ..color = color.withValues(alpha: unit(alpha))
        ..style = width == 0 ? PaintingStyle.fill : PaintingStyle.stroke
        ..strokeWidth = math.max(.65, width * s),
    );
  }

  final ground = Offset(origin.dx, floor - 2 * s);
  if (frame.flash > .01) {
    oval(ground, 150, 37, white, frame.flash * .58);
    oval(ground, 175, 39, gold, frame.flash, width: 7);
    for (var i = 0; i < (reduced ? 4 : 9); i++) {
      final angle = math.pi + i / 8 * math.pi;
      line(
        ground,
        ground + Offset(math.cos(angle) * 110, math.sin(angle) * 65) * s,
        white,
        frame.flash * .85,
        3,
      );
    }
  }
  // Pressure seal and swarf lift before the physical impact: no electric orb.
  if (frame.charge > .01) {
    final load = frame.charge;
    oval(ground, heavy ? 140 : 86, heavy ? 28 : 16, gold, load * .14);
    for (var i = 0; i < (reduced ? 1 : 3); i++) {
      oval(
        ground,
        55 + load * (heavy ? 98 : 48) + i * 18,
        10 + load * 17 + i * 3,
        gold,
        load * (.7 - i * .16),
        width: 2.5,
      );
    }
    for (var i = 0; i < (reduced ? 4 : 8); i++) {
      final angle = i * math.pi / 4 + t * 1.8;
      final radius = (heavy ? 120 : 84) * s;
      final p =
          ground +
          Offset(math.cos(angle) * radius, math.sin(angle) * radius * .19);
      line(
        p,
        p + Offset(math.cos(angle) * 13, math.sin(angle) * 4) * s,
        white,
        load * .8,
        3,
      );
    }
    if (heavy && !reduced) {
      for (var i = 0; i < 4; i++) {
        final x = (i - 1.5) * 66,
            rise = load * (20 + 11 * math.sin(i * 2 + t * 9));
        final point = ground + Offset(x, -rise) * s;
        final stone = Path()
          ..moveTo(point.dx - 7 * s, point.dy)
          ..lineTo(point.dx, point.dy - 12 * s)
          ..lineTo(point.dx + 12 * s, point.dy - 6 * s)
          ..lineTo(point.dx + 8 * s, point.dy + 5 * s)
          ..close();
        path(stone, steel, load * .8);
        path(stone, gold, load * .8, width: 1.5);
      }
    }
  }
  // Steam escapes the actual radiator banks while charging or shutting down.
  if (frame.smoke > .02) {
    for (final side in [-1, 1]) {
      for (var i = 0; i < (reduced ? 2 : 4); i++) {
        final u = (t * 1.7 + i / 4) % 1;
        final p = origin + Offset(side * (66 + 10 * u), -110 - u * 55) * s;
        oval(p, 5 + u * 11, 4 + u * 9, steel, frame.smoke * (1 - u) * .32);
      }
    }
  }
  if ({'attack', 'quick', 'playful'}.contains(frame.action) &&
      pose.weapon.isEmpty &&
      frame.discharge > .02) {
    final fist = titanFist(pose, origin, s, facing, false);
    for (var i = 0; i < (reduced ? 1 : 3); i++) {
      final u = (t * 3.3 + i / 3) % 1;
      oval(
        fist + Offset(facing * u * 24 * s, 0),
        9 + u * 23,
        13 + u * 30,
        gold,
        frame.discharge * (1 - u) * .75,
        width: 2.8,
      );
    }
    for (var i = 0; i < (reduced ? 3 : 6); i++) {
      final a = -.9 + i * .32;
      line(
        fist + Offset(facing * 12, 0) * s,
        fist + Offset(facing * math.cos(a) * 38, math.sin(a) * 30) * s,
        white,
        frame.discharge * .65,
        2,
      );
    }
  }
  if (frame.trail > .01) {
    for (var i = 0; i < (reduced ? 2 : 6); i++) {
      final u = (t * 2 + i / 6) % 1;
      final p = ground + Offset(-facing * (20 + u * 135), -3 - u * 16) * s;
      oval(p, 5 + u * 14, 3 + u * 6, steel, frame.trail * (1 - u) * .4);
    }
  }
  if ((skill || heavy) && frame.shockwave > .01) {
    final release = heavy ? .62 : .46;
    final travel = unit((t - release) / (.9 - release));
    final end = Offset.lerp(
      ground,
      Offset(target.dx, floor - 2 * s),
      smooth(travel),
    )!;
    final envelope = frame.shockwave;
    final waveCount = reduced
        ? 1
        : heavy
        ? 4
        : 2;
    for (var i = 0; i < waveCount; i++) {
      final u = unit(travel - i * .055);
      final radius = (heavy ? 32 : 18) + (heavy ? 300 : 150) * u;
      oval(
        ground,
        radius,
        radius * .18,
        gold,
        envelope * (1 - u * .55) * (1 - i * .15),
        width: heavy ? 8 : 3,
      );
    }
    // A jagged fracture joins the ground strike to the opponent. It is not a beam.
    final crack = Path()..moveTo(ground.dx, floor);
    for (var i = 1; i <= 12; i++) {
      final u = i / 12;
      crack.lineTo(
        ground.dx + (end.dx - ground.dx) * u,
        floor + (i.isEven ? -6 : 7) * s,
      );
    }
    path(crack, dark, envelope, width: heavy ? 13 : 9);
    path(crack, gold, envelope * .9, width: heavy ? 4 : 2.5);
    for (
      var i = 0;
      i <
          (reduced
              ? 2
              : heavy
              ? 7
              : 4);
      i++
    ) {
      final back = i * 22 * facing * s;
      final x = end.dx - back;
      final height = (heavy ? 42 : 24) * (1 - i / (heavy ? 10 : 7));
      final shard = Path()
        ..moveTo(x - 12 * s, floor)
        ..lineTo(x - 5 * s, floor - height * s)
        ..lineTo(x + 9 * s, floor - (height + 5) * s)
        ..lineTo(x + 17 * s, floor)
        ..close();
      path(shard, dark, envelope);
      path(shard, steel, envelope * .9, width: 2);
      line(
        Offset(x - 5 * s, floor - height * s),
        Offset(x + 5 * s, floor - 2 * s),
        gold,
        envelope * .9,
        2.5,
      );
    }
    if (t >= .9) {
      final u = unit((t - .9) / .1), burst = math.sin(u * math.pi);
      final hit = Offset(target.dx, floor);
      for (
        var i = 0;
        i <
            (reduced
                ? 2
                : heavy
                ? 5
                : 3);
        i++
      ) {
        final x = target.dx + (i - (heavy ? 2 : 1)) * 25 * s;
        final height =
            (heavy ? 240 : 68) *
            burst *
            (1 - .12 * (i - (heavy ? 2 : 1)).abs());
        final p = Path()
          ..moveTo(x - 16 * s, floor)
          ..lineTo(x - 12 * s, floor - height * s)
          ..lineTo(x + 5 * s, floor - (height + 9 * burst) * s)
          ..lineTo(x + 20 * s, floor)
          ..close();
        path(p, dark, 1 - u * .6);
        final face = Path()
          ..moveTo(x - 12 * s, floor - height * s)
          ..lineTo(x + 5 * s, floor - (height + 9 * burst) * s)
          ..lineTo(x + 5 * s, floor)
          ..lineTo(x - 8 * s, floor)
          ..close();
        path(face, steel, burst * .65);
        path(p, gold, burst * .9, width: 3);
        line(
          Offset(x + 5 * s, floor - (height + 9 * burst) * s),
          Offset(x + 5 * s, floor),
          steel,
          burst * .8,
          4,
        );
      }
      oval(
        hit,
        35 + (heavy ? 175 : 70) * u,
        9 + (heavy ? 38 : 18) * u,
        gold,
        (1 - u) * .9,
        width: heavy ? 6 : 3,
      );
      oval(
        hit + Offset(0, -25 * s),
        heavy ? 65 : 26,
        heavy ? 45 : 20,
        white,
        burst * .2,
      );
      for (var i = 0; i < (reduced ? 4 : 12); i++) {
        final angle = math.pi + (i + .5) / 12 * math.pi;
        final radius = (heavy ? 120 : 56) * u;
        final p =
            hit +
            Offset(
                  math.cos(angle) * radius,
                  math.sin(angle) * radius + 60 * u * u,
                ) *
                s;
        c.drawRect(
          Rect.fromCenter(
            center: p,
            width: (i.isEven ? 7 : 4) * s,
            height: 5 * s,
          ),
          paint
            ..style = PaintingStyle.fill
            ..color = (i.isEven ? gold : steel).withValues(alpha: 1 - u),
        );
      }
    }
  }
  if (frame.shield > .01) {
    final hold = frame.shield, hit = frame.shieldHit;
    final center = origin + Offset(facing * (62 - 9 * hit), -13) * s;
    c.save();
    c.translate(center.dx, center.dy);
    c.scale(facing * s * hold, s * hold);
    for (var i = -1; i <= 1; i++) {
      final x = i * 43.0, fold = (1 - hold) * 60;
      final p = Path()
        ..moveTo(x - 25, -103 + fold)
        ..lineTo(x + 17, -110 + fold)
        ..lineTo(x + 28, -83 + fold)
        ..lineTo(x + 25, 78 - fold)
        ..lineTo(x + 2, 103 - fold)
        ..lineTo(x - 27, 75 - fold)
        ..close();
      c.drawPath(
        p,
        paint
          ..style = PaintingStyle.fill
          ..color = dark.withValues(alpha: .88),
      );
      c.drawPath(
        p,
        paint
          ..style = PaintingStyle.stroke
          ..strokeWidth = 6
          ..color = steel,
      );
      c.drawPath(
        p,
        paint
          ..strokeWidth = 2.2
          ..color = white,
      );
      final face = Path()
        ..moveTo(x - 18, -79)
        ..lineTo(x + 12, -86)
        ..lineTo(x + 18, 58)
        ..lineTo(x, 80)
        ..lineTo(x - 19, 61)
        ..close();
      c.drawPath(
        face,
        paint
          ..style = PaintingStyle.fill
          ..color = gold.withValues(alpha: .13 + .25 * hit),
      );
      for (var j = 0; j < 3; j++) {
        c.drawLine(
          Offset(x - 13, 22 + j * 12),
          Offset(x + 12, 18 + j * 12),
          paint
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3
            ..color = gold.withValues(alpha: .8),
        );
      }
      // A slit leaves the pilot's face legible through the assembled plates.
      c.drawLine(
        Offset(x - 16, -52),
        Offset(x + 15, -54),
        paint
          ..strokeWidth = 9
          ..color = dark,
      );
      c.drawLine(
        Offset(x - 14, -52),
        Offset(x + 14, -54),
        paint
          ..strokeWidth = 2
          ..color = gold,
      );
    }
    c.restore();
    if (hit > .01) {
      final contact = center + Offset(facing * 62 * s, -10 * s);
      oval(
        contact,
        16 + 25 * (1 - hit),
        22 + 35 * (1 - hit),
        white,
        hit,
        width: 3,
      );
      for (var i = 0; i < 5; i++) {
        final a = i * 1.25 + t * 4;
        line(
          contact,
          contact + Offset(math.cos(a) * 26, math.sin(a) * 26) * s,
          gold,
          hit,
          2.5,
        );
      }
    }
  }
  if (frame.sparks > .01) {
    for (var i = 0; i < (reduced ? 4 : 9); i++) {
      final u = (t * 1.3 + i / 9) % 1;
      final p =
          origin + Offset((i - 4) * 22 * u, -125 - u * 65 + 70 * u * u) * s;
      line(p, p + Offset(3, 6) * s, gold, frame.sparks * (1 - u), 3);
    }
  }
}
