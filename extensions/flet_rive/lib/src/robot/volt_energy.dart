import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Screen-readable electrical shapes. All geometry is bounded and sampled
/// from the scene clock: no extra tickers, images, blur layers or particle pool.
class VoltEnergyPainter {
  VoltEnergyPainter(this.canvas, this.scale, this.t, {this.reduced = false});
  final Canvas canvas;
  final double scale, t;
  final bool reduced;
  final Paint paint = Paint()..strokeCap = StrokeCap.round;
  static const cyan = Color(0xFF4CE8FF);
  static const white = Color(0xFFF1FFFF);
  static const blue = Color(0xFF188BEB);
  static const gold = Color(0xFFFFE9A0);

  double unit(double value) => value.clamp(0.0, 1.0);
  void stroke(Path path, double width, Color color, double alpha) {
    if (alpha <= .001) return;
    canvas.drawPath(
      path,
      paint
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1, width * scale)
        ..color = color.withValues(alpha: unit(alpha)),
    );
  }

  void line(Offset a, Offset b, double width, Color color, double alpha) =>
      stroke(
        Path()
          ..moveTo(a.dx, a.dy)
          ..lineTo(b.dx, b.dy),
        width,
        color,
        alpha,
      );

  void disc(Offset p, double radius, Color color, double alpha) {
    if (radius <= 0 || alpha <= .001) return;
    canvas.drawCircle(
      p,
      radius * scale,
      paint
        ..style = PaintingStyle.fill
        ..color = color.withValues(alpha: unit(alpha)),
    );
  }

  void ring(
    Offset p,
    double radius,
    double alpha, {
    double squash = 1,
    double width = 2.5,
    Color color = cyan,
  }) {
    if (radius <= 0 || alpha <= .001) return;
    canvas.drawOval(
      Rect.fromCenter(
        center: p,
        width: 2 * radius * scale,
        height: 2 * radius * scale * squash,
      ),
      paint
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1, width * scale)
        ..color = color.withValues(alpha: unit(alpha)),
    );
  }

  void transfer(Offset core, Offset left, Offset right, double strength) {
    if (strength < .01) return;
    for (final tip in [left, right]) {
      final side = tip.dx < core.dx ? -1 : 1;
      final path = Path()
        ..moveTo(core.dx + side * 22 * scale, core.dy - 9 * scale)
        ..cubicTo(
          core.dx + side * 86 * scale,
          core.dy - 18 * scale,
          tip.dx + side * 20 * scale,
          tip.dy + 42 * scale,
          tip.dx,
          tip.dy,
        );
      stroke(path, 8, blue, strength * .26);
      stroke(path, 2.8, cyan, strength * .85);
    }
  }

  /// A contained capacitor, with circulating rings that contract at release.
  void capacitor(Offset center, double charge, {required bool storm}) {
    if (charge < .015) return;
    final radius = (storm ? 15 + 29 * charge : 9 + 18 * charge);
    disc(center, radius * 1.7, blue, charge * .15);
    disc(center, radius * 1.25, cyan, charge * .2);
    disc(center, radius, cyan, charge * .62);
    disc(center, radius * .56, white, charge * .94);
    disc(
      center + Offset(-radius * .18, -radius * .2) * scale,
      radius * .17,
      white,
      charge,
    );
    final count = reduced ? 1 : (storm ? 3 : 2);
    for (var i = 0; i < count; i++) {
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(t * (i.isEven ? 6 : -5) + i * math.pi / count);
      ring(
        Offset.zero,
        radius + 7 + i * 5,
        charge * .9,
        squash: .34 + i * .15,
        width: storm ? 3 : 2.3,
        color: i == 1 ? gold : cyan,
      );
      canvas.restore();
    }
    for (var i = 0; i < (reduced ? 3 : 6); i++) {
      final angle = t * 7 + i * math.pi / 3;
      final dir = Offset(math.cos(angle), math.sin(angle));
      line(
        center + dir * (radius + 8) * scale,
        center + dir * (radius + 17) * scale,
        2,
        white,
        charge * .65,
      );
    }
  }

  void muzzle(Offset point, double load, double release, double facing) {
    if (load + release < .02) return;
    for (var i = 0; i < 3; i++) {
      ring(
        point + Offset(facing * i * 6 * scale, 0),
        9 + i * 3 + release * 7,
        (load * .7 + release) * (1 - i * .16),
        squash: .72,
        width: 2.4,
        color: i == 1 ? gold : cyan,
      );
    }
    disc(point, 8 + release * 7, white, unit(load * .55 + release));
  }

  /// A compact pulse with a moving head, rather than the same full beam used
  /// by the skill. The head reaches the target at the arena impact boundary.
  void pulse(Offset from, Offset target, double travel, double strength) {
    if (strength < .01) return;
    final head = Offset.lerp(from, target, unit(travel))!;
    final tail = Offset.lerp(from, target, unit(travel - .17))!;
    line(tail, head, 17, blue, strength * .28);
    line(tail, head, 7, cyan, strength);
    line(Offset.lerp(tail, head, .3)!, head, 2.8, white, strength);
    disc(head, 13, blue, strength * .24);
    disc(head, 8, cyan, strength);
    disc(head, 3.8, white, strength);
    ring(head, 11, strength * .8, squash: .72);
  }

  void beam(
    Offset from,
    Offset target,
    double extension,
    double strength, {
    required bool storm,
  }) {
    if (strength < .01) return;
    final end = Offset.lerp(from, target, unit(extension))!;
    final delta = end - from;
    if (delta.distance < .1) return;
    final normal = Offset(-delta.dy, delta.dx) / delta.distance;
    final path = Path()
      ..moveTo(from.dx, from.dy)
      ..lineTo(end.dx, end.dy);
    stroke(path, storm ? 48 : 31, blue, strength * .19);
    stroke(path, storm ? 28 : 17, cyan, strength * .38);
    stroke(path, storm ? 12 : 7, cyan, strength);
    stroke(path, storm ? 4.8 : 3, white, strength);
    if (!reduced) {
      for (final side in [-1, 1]) {
        final ribbon = Path()..moveTo(from.dx, from.dy);
        for (var i = 1; i <= 12; i++) {
          final u = i / 12;
          final p =
              Offset.lerp(from, end, u)! +
              normal *
                  side.toDouble() *
                  math.sin(u * math.pi) *
                  (7 + 5 * math.sin(u * 19 - t * 38)) *
                  scale;
          ribbon.lineTo(p.dx, p.dy);
        }
        stroke(ribbon, storm ? 3.2 : 2.3, white, strength * .8);
      }
    }
    disc(end, storm ? 19 : 12, white, strength * .75);
  }

  void impact(
    Offset center,
    double strength,
    double progress, {
    bool storm = false,
  }) {
    if (strength < .01) return;
    final radius = (storm ? 24 : 12) + (storm ? 60 : 29) * unit(progress);
    disc(center, radius * .75, cyan, strength * .22);
    disc(center, storm ? 21 : 9, white, strength);
    ring(center, radius, strength, width: storm ? 4 : 2.8, color: white);
    ring(center, radius * 1.3, strength * .62, squash: .72, color: gold);
    for (var i = 0; i < (reduced ? 4 : 8); i++) {
      final a = i * math.pi / 4 + .25;
      final dir = Offset(math.cos(a), math.sin(a));
      line(
        center + dir * radius * .45 * scale,
        center + dir * radius * (i.isEven ? 1.1 : .85) * scale,
        storm ? 3.2 : 2,
        i.isEven ? white : cyan,
        strength,
      );
    }
  }

  void dashContact(Offset center, double strength, double facing) {
    if (strength < .02) return;
    for (var i = 0; i < 2; i++) {
      final radius = (30 + i * 14) * scale;
      final rect = Rect.fromCenter(
        center: center,
        width: radius * 1.2,
        height: radius * 2,
      );
      canvas.drawArc(
        rect,
        facing > 0 ? -1.15 : math.pi - 1.15,
        2.3,
        false,
        paint
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(1.4, (5 - i) * scale)
          ..color = (i == 0 ? white : cyan).withValues(
            alpha: strength * (1 - i * .2),
          ),
      );
    }
    line(
      center - Offset(facing * 33 * scale, 0),
      center + Offset(facing * 39 * scale, 0),
      7,
      cyan,
      strength,
    );
  }

  void shield(
    Offset center,
    double strength,
    double hit,
    double facing, {
    bool preview = false,
  }) {
    if (strength < .01) return;
    final radius = 139 * strength;
    Offset surface(double angle) {
      final front = math.pow(math.max(0, math.cos(angle) * facing), 8);
      final deform = 1 - .23 * hit * front;
      final flow = 1 + .018 * math.sin(angle * 5 + t * 26);
      return center +
          Offset(math.cos(angle), math.sin(angle) * 1.06) *
              radius *
              scale *
              deform *
              flow;
    }

    final shell = Path();
    final segments = reduced ? 16 : 32;
    for (var i = 0; i <= segments; i++) {
      final p = surface(i / segments * math.pi * 2);
      if (i == 0) {
        shell.moveTo(p.dx, p.dy);
      } else {
        shell.lineTo(p.dx, p.dy);
      }
    }
    shell.close();
    canvas.drawPath(
      shell,
      paint
        ..style = PaintingStyle.fill
        ..color = blue.withValues(alpha: (.12 + .1 * hit) * strength),
    );
    stroke(shell, 10 + 6 * hit, cyan, strength * (.2 + .16 * hit));
    stroke(shell, 3.8 + 2 * hit, hit > .3 ? white : cyan, strength * .94);
    if (!reduced) {
      canvas.save();
      canvas.clipPath(shell);
      for (var i = -2; i <= 2; i++) {
        final shift = (i * 44 + (t * 38) % 44) * scale;
        line(
          center + Offset(-radius * scale, shift),
          center + Offset(radius * scale, shift - 24 * scale),
          1.3,
          cyan,
          strength * .23,
        );
        line(
          center + Offset(shift, -radius * scale),
          center + Offset(shift - 24 * scale, radius * scale),
          1.3,
          cyan,
          strength * .18,
        );
      }
      canvas.restore();
    }
    for (var i = 0; i < (reduced ? 3 : 6); i++) {
      final angle = i * math.pi / 3 + t * 2.2;
      final p = surface(angle), q = surface(angle + .32);
      final path = Path()
        ..moveTo(p.dx, p.dy)
        ..lineTo(q.dx, q.dy);
      stroke(path, 5, white, strength * .8);
      disc(p, 3.4, cyan, strength);
    }
    final contact = surface(facing < 0 ? math.pi : 0);
    if (preview && t > .36 && t < .56) {
      final flight = unit((t - .36) / .2);
      final start = contact + Offset(facing * 118, -46) * scale;
      final head = Offset.lerp(start, contact, flight)!;
      line(
        Offset.lerp(start, contact, math.max(0, flight - .18))!,
        head,
        5.5,
        gold,
        strength,
      );
      disc(head, 7, gold, strength);
    }
    if (hit > .01) {
      impact(contact, hit, 1 - hit);
      final reflected =
          contact + Offset(facing * (30 + 38 * (1 - hit)), -45) * scale;
      line(contact, reflected, 2.5, white, hit * .85);
    }
  }
}
