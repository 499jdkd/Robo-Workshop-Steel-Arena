import 'dart:math' as math;
import 'package:material_ui/material_ui.dart';
import 'game_motion.dart';

/// Authored timelines on the existing articulated rigs. t includes charge,
/// release and recovery; each pose is absolute, never accumulated per frame.
void signaturePose(GamePose p, String id, double t, {bool ultimate = true}) {
  final charge = smooth(t / .28);
  final strike = math.sin(math.pi * unit((t - .28) / .55));
  final release = smooth((t - .28) / .22);
  final fade = 1 - smooth((t - .83) / .17);
  final power = ultimate ? 1.0 : .62;
  final a = charge * fade * power, b = strike * power;
  p.mode = t < .28 ? 4 : 2;
  p.weapon = '';
  p.deploy = 0;
  p.smile = 0;
  p.focus = 1;
  p.brow = .2 * a;
  p.aura = .3 * pulse(t, 0, .45) * power;
  switch (id) {
    case 'spark':
      p.x += 65 * b; p.body = -.22 * a + .4 * b;
      p.head = -.16 * a; p.weapon = 'plasma'; p.deploy = charge * fade;
      p.armR = -1.5; p.foreR = .14 * math.sin(t * 35);
      p.y -= 15 * b; p.extra['joint0'] = t * 14;
    case 'volt':
      p.y -= (36 * a + 28 * b); p.armL = 1.3 * a; p.armR = -1.3 * a;
      p.head = .16 * math.sin(t * 25) * a; p.body = -.12 * a;
      p.extra['joint0'] = -.65 * a; p.extra['joint1'] = .65 * a;
      p.extra['jet'] = 1 + a;
    case 'flora':
      p.armL = 1.1 * a; p.armR = -1.1 * a; p.foreL = -.8 * a;
      p.foreR = .8 * a; p.head = -.25 * a; p.smile = 1; p.focus = 0;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = (i.isEven ? 1 : -1) * a * .8;
    case 'forge':
      p.y += 12 * a; p.body = .25 * b;
      p.armL = 1.8 * a - 1.4 * release * fade; p.armR = -p.armL;
      p.foreL = -1.1 * a; p.foreR = 1.1 * a;
      p.extra['joint0'] = .55 * a; p.extra['joint1'] = -.55 * a;
    case 'nova':
      p.y -= 38 * a; p.rotation = -.16 * b;
      p.armL = .7 * a; p.armR = -.7 * a;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = i * math.pi / 3 + t * 12 * a;
      p.extra['bodyscaleX'] = 1 - .14 * a;
    case 'glacier':
      p.y -= 18 * a; p.head = -.16 * a;
      p.armL = .6 * a; p.armR = -1.4 * a;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = (i - 2.5) * .24 * a;
      p.extra['fins'] = 1;
    case 'aegis':
      p.y += 15 * a; p.armL = .8 * a; p.armR = -.8 * a;
      p.shield = a; p.body = -.1 * a;
      p.extra['joint0'] = -.8 * a; p.extra['joint1'] = .8 * a;
    case 'solar':
      p.y -= 45 * a; p.armL = 2 * a; p.armR = -2 * a;
      p.head = -.2 * a;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = i * math.pi / 4 + t * 8;
    case 'titan':
      p.armL = (2.6 * charge - 2.3 * release) * fade;
      p.armR = -p.armL; p.foreL = -.4 * a; p.foreR = .4 * a;
      p.y += (-25 * charge + 45 * release) * fade;
      p.body = .35 * release * fade; p.head = .2 * release * fade;
      p.extra['joint0'] = -.25 * a; p.extra['joint1'] = .25 * a;
    case 'arachna':
      p.y -= 32 * a; p.body = -.14 * a;
      p.armL = 1.5 * a; p.armR = -1.5 * a;
      // The two front assemblies cross around the charge node.
      p.extra['joint0'] = -1.2 * a; p.extra['joint1'] = 1.2 * a;
      p.extra['joint8'] = .9 * a; p.extra['joint9'] = -.9 * a;
      for (var i = 2; i < 6; i++) p.extra['joint$i'] = (i.isEven ? -.4 : .4) * a;
    case 'phantom':
      p.y -= 26 * a; p.x += 75 * b; p.rotation = -.5 * b;
      p.armL = 1.2 * a; p.armR = -1.8 * b;
      p.extra['joint0'] = -1.2 * a; p.extra['joint1'] = 1.2 * a;
    case 'falcon':
      p.y -= 90 * math.sin(math.pi * t) * power;
      p.rotation = math.sin(t * math.pi * 2) * .55 * power;
      p.x += 50 * b;
      p.extra['joint0'] = -.95 * a; p.extra['joint1'] = .95 * a;
      p.extra['joint2'] = .65 * b; p.extra['joint3'] = -.65 * b;
    case 'cyclops':
      p.eyeY = .4; p.head = -.06 * a;
      p.x -= 38 * math.exp(-math.max(0, t - .3) * 12) * release;
      p.extra['joint0'] = -.45 * a; p.extra['joint1'] = .45 * a;
      p.extra['joint2'] = .2 * a; p.extra['joint3'] = -.2 * a;
    case 'medic':
      p.y -= 22 * a; p.armL = 1.5 * a; p.armR = -1.5 * a;
      p.smile = 1; p.focus = 0;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = i * math.pi / 4 + t * (i < 4 ? 4 : 28);
    case 'atlas':
      p.y -= 60 * b; p.body = .4 * release * fade;
      p.armL = 2.2 * a - 2.6 * release * fade; p.armR = -p.armL;
      p.foreL = -1.3 * a; p.foreR = 1.3 * a;
      p.extra['joint0'] = -.4 * a; p.extra['joint1'] = .4 * a;
    case 'cerberus':
      p.x += 85 * b; p.y -= 30 * b; p.body = -.2 * a;
      for (var i = 0; i < 3; i++) p.extra['joint$i'] = (i - 1) * .65 * a;
      for (var i = 4; i < 8; i++) p.extra['joint$i'] = (i.isEven ? 1 : -1) * b;
    case 'cobra':
      p.y -= 18 * a; p.head = -.45 * a;
      for (var i = 0; i < 8; i++) {
        p.extra['joint$i'] = math.sin(t * 9 - i * .8) * .65 * a;
        p.extra['segmentY$i'] = 95 - 24 * a + i * a * 3;
      }
    case 'phoenix':
      p.y -= 65 * math.sin(math.pi * t) * power; p.rotation = -.2 * b;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = (i.isEven ? 1 : -1) * (1.1 * a + .3 * math.sin(t * 15));
    case 'driller':
      p.x += 75 * b; p.y += 20 * b; p.body = .3 * a;
      p.extra['joint4'] = t * 90; p.extra['joint0'] = -.25 * a;
      p.armR = -1.5 * a; p.foreR = .3 * a;
    case 'ninja':
      p.y += 22 * a - 45 * b; p.x += 80 * b;
      p.rotation = .6 * b; p.armL = .9 * a; p.armR = -2.4 * b;
      p.foreR = -.8 * a; p.extra['joint0'] = -.8 * a; p.extra['joint1'] = .8 * a;
    case 'specter':
      p.y -= 30 * a; p.body = -.35 * b;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = i * math.pi / 4 - t * 9;
      p.extra['bodyscaleX'] = 1 - .3 * b;
    case 'magneto':
      p.armL = 1.8 * a; p.armR = -1.8 * a; p.y -= 20 * a;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = i * math.pi / 3 - t * 6;
    case 'rocketeer':
      p.y += 16 * a; p.body = -.12 * math.sin(t * 35) * b;
      p.extra['joint0'] = -.8 * a; p.extra['joint1'] = .8 * a;
      p.armL = .4 * a; p.armR = -.4 * a;
    case 'octopus':
      p.y -= 20 * a;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = (i - 3.5) * .22 * a + math.sin(t * 12 - i) * .3;
      p.armL = 1.5 * a; p.armR = -1.5 * a; p.smile = 1;
    case 'scarab':
      p.y += 12 * a; p.shield = .7 * a;
      p.extra['joint0'] = -1.1 * a; p.extra['joint1'] = 1.1 * a;
      for (var i = 2; i < 6; i++) p.extra['joint$i'] = (i.isEven ? .7 : -.7) * a;
    case 'orbit':
      p.y -= 35 * a; p.rotation = .35 * math.sin(t * 12) * a;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = i * math.pi / 4 + t * 20;
    case 'guardian':
      p.armL = .25 * a; p.armR = -1.3 * a; p.foreR = -.65 * a;
      p.y += 18 * a; p.shield = a; p.head = .12 * a;
    case 'goliath':
      p.y += 20 * a; p.body = -.26 * b;
      for (var i = 0; i < 4; i++) p.extra['joint$i'] = (i.isEven ? -.65 : .65) * a;
      p.extra['joint4'] = -1.1 * a; p.extra['joint5'] = 1.1 * a;
    case 'chronos':
      p.y -= 20 * a; p.armL = 1.2 * a; p.armR = -1.2 * a;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = i * math.pi / 4 + (t < .3 ? t * 24 : 7.2);
    case 'omega':
      p.extra['bodyscaleX'] = 1 + .35 * a;
      p.extra['bodyscaleY'] = 1 - .2 * a; p.y += 15 * a;
      p.armL = 1.6 * a; p.armR = -1.6 * a;
      for (var i = 0; i < 8; i++) p.extra['joint$i'] = (i.isEven ? -1 : 1) * a * (i < 4 ? 1.2 : .65);
    case 'storm':
      p.y -= 70 * a; p.rotation = .35 * math.sin(t * 18) * a;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = i * math.pi / 3 + t * 18;
    case 'chameleon':
      p.y += 16 * a; p.x += 25 * b; p.head = -.28 * a;
      for (var i = 0; i < 6; i++) p.extra['joint$i'] = (i.isEven ? 1 : -1) * .55 * a;
      p.extra['bodyscaleY'] = 1 - .15 * a;
  }
  if (!ultimate) {
    // The skill is a short, one-sided counter. The super reserves the full
    // body windup, flight/transform and simultaneous articulated assemblies.
    p.y *= .2; p.x *= .55; p.rotation *= .25;
    p.armL = .2; p.foreL = -.3;
    if (id == 'titan' || id == 'atlas' || id == 'forge') {
      p.armR = -.5 * charge - 1.2 * strike; p.foreR = -.7 * charge;
      p.body = .18 * strike;
    }
    if (id == 'volt') { p.armR = -1.2 * a; p.extra['joint0'] = 0; }
    if (id == 'arachna') { p.extra['joint0'] = -.7 * a; p.extra['joint1'] = 0; p.extra['joint9'] = 0; }
    if (id == 'omega') { p.extra['bodyscaleX'] = 1; p.extra['bodyscaleY'] = 1; }
  }
}

/// Distinct emitters and paths, drawn in bounded loops on one native canvas.
void paintSignature(Canvas c, String id, Offset from, Offset to, double ground,
    double s, double t, Color color, {bool ultimate = true, bool reduced = false}) {
  final q = unit((t - .25) / .6), charge = pulse(t, 0, .45);
  final fade = 1 - smooth((t - .85) / .15);
  final strength = (ultimate ? 1.0 : .62) * fade;
  if (strength <= 0) return;
  final p = Paint()..strokeCap = StrokeCap.round;
  void line(Offset a, Offset b, double width, [Color? tint]) => c.drawLine(a, b,
    p..color = (tint ?? color).withValues(alpha: .85 * strength)..style = PaintingStyle.stroke..strokeWidth = math.max(1, width * s));
  void ring(Offset a, double radius, {double squash = 1, double width = 3, Color? tint}) => c.drawOval(
    Rect.fromCenter(center: a, width: radius * 2 * s, height: radius * 2 * s * squash),
    p..color = (tint ?? color).withValues(alpha: .8 * strength)..style = PaintingStyle.stroke..strokeWidth = math.max(1, width * s));
  void orb(Offset a, double radius, [Color? tint]) {
    c.drawCircle(a, radius * s, p..color = (tint ?? color).withValues(alpha: .25 * strength)..style = PaintingStyle.fill);
    c.drawCircle(a, radius * .35 * s, p..color = Colors.white.withValues(alpha: strength));
  }
  void arc(Offset a, Offset b, int seed, {double width = 3}) {
    final path = Path()..moveTo(a.dx, a.dy);
    for (var j = 1; j <= 12; j++) {
      final point = Offset.lerp(a, b, j / 12)!;
      path.lineTo(point.dx, point.dy + (j == 12 ? 0 : math.sin(j * 2.7 + t * 80 + seed) * 15 * s));
    }
    c.drawPath(path, p..color = color.withValues(alpha: strength)..style = PaintingStyle.stroke..strokeWidth = width * s);
  }
  final center = Offset.lerp(from, to, q)!;
  if (!ultimate) {
    switch (id) {
      case 'volt':
      case 'storm':
        if (q > 0) arc(from, center, 1); ring(center, 18 * q);
      case 'arachna':
        line(from + Offset(0, -25 * s), center, 2);
        for (var i = 0; i < 3; i++) {
          final angle = i * math.pi * 2 / 3;
          line(center, center + Offset(math.cos(angle), math.sin(angle)) * 25 * s, 2);
        }
        ring(center, 20, width: 1);
      case 'titan':
      case 'atlas':
      case 'forge':
        final rect = Rect.fromCircle(center: center, radius: 36 * s);
        c.drawArc(rect, -.8 + q * 2, 1.8, false,
          p..color = color..style = PaintingStyle.stroke..strokeWidth = 9 * s);
        if (q > .7) ring(Offset(to.dx, ground), 28, squash: .25);
      case 'falcon':
      case 'phoenix':
        for (final side in [-1, 1]) {
          final point = center + Offset(0, side * 15 * s * math.sin(q * math.pi));
          line(point - Offset(30 * s, side * 15 * s), point, 5);
        }
      case 'phantom':
      case 'specter':
        ring(from + Offset(-45 * s, 0), 32, squash: 1.4, width: 2);
        line(center + Offset(0, -22 * s), center + Offset(0, 22 * s), 4);
      case 'medic':
      case 'octopus':
        final drone = from + Offset(math.sin(t * 8) * 40 * s, -45 * s);
        c.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: drone, width: 28 * s, height: 18 * s), Radius.circular(5 * s)), p..color = const Color(0xFFCAF8EB)..style = PaintingStyle.fill);
        line(drone + Offset(-20 * s, -8 * s), drone + Offset(20 * s, -8 * s), 2);
        line(drone, from, 3, Colors.greenAccent);
      case 'flora':
        ring(from, 30, squash: .65, tint: Colors.greenAccent);
        for (final side in [-1, 1]) {
          c.drawOval(Rect.fromCenter(center: from + Offset(side * 18 * s, -8 * s), width: 24 * s, height: 12 * s),
            p..color = const Color(0xAA7DFFB5)..style = PaintingStyle.fill);
        }
        orb(center, 8, Colors.greenAccent);
      case 'glacier':
        for (var i = 0; i < 6; i++) {
          final angle = i * math.pi / 3 + q;
          line(center, center + Offset(math.cos(angle), math.sin(angle)) * 26 * s, 3, const Color(0xFFBDF6FF));
        }
      case 'aegis':
      case 'guardian':
      case 'scarab':
        final shield = Rect.fromCenter(center: from + Offset(40 * s, 0), width: 50 * s, height: 85 * s);
        c.drawRRect(RRect.fromRectAndRadius(shield, Radius.circular(12 * s)), p..color = color.withValues(alpha:.3)..style = PaintingStyle.fill);
        c.drawRRect(RRect.fromRectAndRadius(shield, Radius.circular(12 * s)), p..color = color..style = PaintingStyle.stroke..strokeWidth = 3 * s);
        line(center + Offset(0, -16 * s), center + Offset(0, 16 * s), 5);
      case 'spark':
      case 'cerberus':
        line(center - Offset(28 * s, 0), center, 7); orb(center, 11);
      case 'ninja':
        line(to + Offset(-35 * s, 30 * s), to + Offset(35 * s * q, -30 * s * q), 5);
      case 'nova':
      case 'cyclops':
        if (q > 0) { line(from, center, 6); line(from, center, 1, Colors.white); }
        ring(to, 18, width:1);
      case 'solar':
        for (var i = 0; i < 3; i++) {
          final end = center + Offset(0, (i - 1) * 12 * s);
          line(from, end, 3, Colors.amberAccent);
        }
      case 'cobra':
        final path = Path()..moveTo(from.dx, from.dy);
        for (var i = 1; i <= 16; i++) {
          final point = Offset.lerp(from, center, i / 16)!;
          path.lineTo(point.dx, point.dy + math.sin(i * .6 + t * 12) * 13 * s);
        }
        c.drawPath(path, p..color = color..style = PaintingStyle.stroke..strokeWidth = 3 * s);
      case 'driller':
        for (var i = 0; i < 3; i++) ring(center + Offset(i * 8 * s, 0), 14 - i * 3, squash: .5);
      case 'magneto':
        c.drawArc(Rect.fromCircle(center: center, radius: 24 * s), q * 5, 4.5, false,
          p..color = color..style = PaintingStyle.stroke..strokeWidth = 5 * s);
        line(center, from, 1);
      case 'rocketeer':
      case 'goliath':
        final rocket = center + Offset(0, -30 * s * math.sin(q * math.pi));
        line(rocket - Offset(20 * s, 0), rocket, 8, Colors.orangeAccent); orb(rocket, 7);
      case 'orbit':
        ring(center, 28, squash: .3, width: 4);
      case 'chronos':
        ring(center, 22, width: 2);
        line(center, center + Offset(math.cos(t * 12), math.sin(t * 12)) * 20 * s, 3);
      case 'omega':
        line(from + Offset(0, 15 * s), center, 8); ring(from, 22, squash: .6);
      case 'chameleon':
        line(to + Offset(-20 * s, -40 * s + q * 80 * s), to + Offset(20 * s, -40 * s + q * 80 * s), 2);
        ring(from, 30, squash: .6, width: 2);
    }
    return;
  }
  if (t < .3) orb(from, 12 + 30 * charge);
  switch (id) {
    case 'spark':
      for (var i = 0; i < (ultimate ? 3 : 2); i++) {
        final u = unit(q * 1.5 - i * .17);
        final point = Offset.lerp(from, to, u)! + Offset(0, math.sin(u * math.pi) * (i - 1) * 35 * s);
        line(point - Offset(25 * s, 0), point, 7); orb(point, 9);
      }
    case 'volt':
      for (var i = 0; i < (reduced ? 1 : 3); i++) {
        final coil = from + Offset((i - 1) * 24 * s, -22 * s);
        ring(coil, 9 + 5 * charge);
        if (q > 0) arc(coil, to + Offset(0, (i - 1) * 26 * s), i);
      }
    case 'flora':
      for (var i = 0; i < 6; i++) {
        final angle = i * math.pi / 3 + t * 3;
        final petal = from + Offset(math.cos(angle), math.sin(angle)) * (35 + 20 * charge) * s;
        c.drawOval(Rect.fromCenter(center: petal, width: 20 * s, height: 38 * s), p..color = const Color(0x887BFFB3)..style = PaintingStyle.fill);
        line(petal, from, 2, Colors.greenAccent);
      }
      ring(from, 65 * q, squash: .45, tint: Colors.greenAccent); orb(center, 12, Colors.greenAccent);
    case 'forge':
      final gap = (1 - math.sin(q * math.pi)) * 60 * s;
      for (final side in [-1, 1]) {
        final point = to + Offset(side * (15 * s + gap), 0);
        c.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: point, width: 20 * s, height: 85 * s), Radius.circular(5 * s)), p..color = const Color(0xFFDBA774)..style = PaintingStyle.fill);
        line(from, point, 5);
      }
    case 'nova':
      ring(to, 65 * (1 - q) + 12, width: 6);
      for (var i = 0; i < 5; i++) {
        final angle = i * math.pi * .4 + q * 8;
        final point = to + Offset(math.cos(angle), math.sin(angle)) * (95 * (1 - q) + 10) * s;
        line(point, to, 3); orb(point, 7);
      }
      orb(to, 30 * math.sin(q * math.pi));
    case 'glacier':
      for (var i = 0; i < (reduced ? 3 : 7); i++) {
        final point = Offset.lerp(from, to, unit(q * 1.4 - i * .06))! + Offset(0, (i - 3) * 10 * s);
        final path = Path()..addPolygon([point + Offset(15 * s, 0), point + Offset(-9 * s, -6 * s), point + Offset(-9 * s, 6 * s)], true);
        c.drawPath(path, p..color = const Color(0xFFBAF4FF)..style = PaintingStyle.fill);
      }
      for (var i = 0; i < 6; i++) {
        final angle = i * math.pi / 3;
        line(to, to + Offset(math.cos(angle), math.sin(angle)) * 55 * s * q, 3, const Color(0xFFBAF4FF));
      }
    case 'aegis':
      for (var i = 0; i < 3; i++) {
        final point = from + Offset((40 + i * 18) * s, 0);
        c.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: point, width: 16 * s, height: (125 - 15 * i) * s * (charge + q).clamp(.1, 1)), Radius.circular(4 * s)), p..color = color.withValues(alpha: .45 * strength)..style = PaintingStyle.fill);
      }
      ring(center, 23 + 20 * q, squash: 1.8);
    case 'solar':
      for (var i = 0; i < (reduced ? 4 : 10); i++) {
        final angle = i * math.pi / 5 + t;
        line(from + Offset(math.cos(angle), math.sin(angle)) * 28 * s,
             from + Offset(math.cos(angle), math.sin(angle)) * (35 + 90 * q) * s, 5, Colors.amberAccent);
      }
      ring(from, 30 + 80 * q, width: 8, tint: Colors.orangeAccent);
    case 'titan':
    case 'atlas':
      final foot = Offset(from.dx, ground);
      for (var i = 0; i < (id == 'titan' ? 3 : 2); i++) ring(foot, 15 + unit(q * 1.4 - i * .2) * (to.dx - from.dx).abs() / math.max(.1, s), squash: .22, width: 5 - i.toDouble());
      if (id == 'atlas') {
        for (var i = 0; i < 5; i++) line(Offset(to.dx - 30 * s + i * 15 * s, ground), to + Offset((i - 2) * 12 * s, -20 * q * s), 4);
      }
    case 'arachna':
      final node = from + Offset(28 * s, -4 * s);
      final upper = from + Offset(-28 * s, -44 * s), lower = from + Offset(-28 * s, 32 * s);
      line(upper, node, 4); line(lower, node, 4); orb(node, 16 + 16 * charge);
      if (q > 0) {
        final end = Offset.lerp(node, to, unit(q * 3))!;
        line(node, end, 22); line(node, end, 6, Colors.white); ring(end, 22 * q);
      }
    case 'phantom':
    case 'specter':
      for (var i = 0; i < 3; i++) {
        final point = Offset.lerp(from, to, unit(q * 1.6 - i * .2))!;
        if (id == 'specter') {
          for (var j = 0; j < 4; j++) line(point + Offset(-20 * s, j * 10 * s), point + Offset(20 * s, j * 10 * s), 1);
        } else {
          ring(point, 15 + i * 6, squash: 1.6);
        }
      }
      if (q > .5) { line(to + Offset(-32 * s, -40 * s), to + Offset(25 * s, 30 * s), 7); line(to + Offset(30 * s, -30 * s), to + Offset(-25 * s, 35 * s), 4); }
    case 'falcon':
    case 'phoenix':
      final apex = Offset(to.dx, math.min(from.dy, to.dy) - 90 * s);
      final point = q < .5 ? Offset.lerp(from, apex, q * 2)! : Offset.lerp(apex, to, (q - .5) * 2)!;
      line(point + Offset(-25 * s, -40 * s), point, 8);
      for (final side in [-1, 1]) line(point, point + Offset(side * 28 * s, -16 * s), 6);
      if (id == 'phoenix') ring(from, 45 + 40 * q, width: 8, tint: Colors.deepOrangeAccent);
      else for (var i = 0; i < 3; i++) line(apex + Offset((i - 1) * 20 * s, 0), Offset.lerp(apex, to, unit(q * 2 - .2 * i))!, 3);
    case 'cyclops':
      ring(to, 20 - 9 * charge); line(to + Offset(-32 * s, 0), to + Offset(32 * s, 0), 1);
      line(to + Offset(0, -32 * s), to + Offset(0, 32 * s), 1);
      if (q > 0) { line(from, to, 16); line(from, to, 3, Colors.white); orb(from, 25 * (1 - q)); }
    case 'medic':
    case 'octopus':
      final count = id == 'octopus' ? 8 : 4;
      for (var i = 0; i < count; i++) {
        final angle = i * math.pi * 2 / count + t * 4;
        final drone = from + Offset(math.cos(angle) * 60, math.sin(angle) * 45) * s;
        line(from, drone, id == 'octopus' ? 4 : 1, Colors.greenAccent);
        c.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: drone, width: 18 * s, height: 12 * s), Radius.circular(3 * s)), p..color = const Color(0xFFE2FFF4)..style = PaintingStyle.fill);
        line(drone + Offset(-12 * s, -8 * s), drone + Offset(12 * s, -8 * s), 2);
      }
      ring(from, 65 * q, squash: .55, tint: Colors.greenAccent);
    case 'cerberus':
      for (var i = 0; i < 3; i++) {
        final start = from + Offset(0, (i - 1) * 30 * s);
        final end = Offset.lerp(start, to, unit(q * 1.6 - i * .15))!;
        arc(start, end, i); orb(end, 11);
      }
    case 'cobra':
      for (var i = 0; i < 4; i++) ring(to + Offset(0, (i - 1.5) * 24 * s), (40 - 23 * q), squash: .4, width: 4);
      arc(from, to, 2, width: 2);
    case 'driller':
      final path = Path()..moveTo(from.dx, ground);
      for (var i = 1; i <= 16; i++) { final point = Offset.lerp(Offset(from.dx, ground), Offset(to.dx, ground), i / 16 * q)!; path.lineTo(point.dx, point.dy + math.sin(i * 2.4) * 8 * s); }
      c.drawPath(path, p..color = color..style = PaintingStyle.stroke..strokeWidth = 4 * s);
      ring(center, 20, squash: .4); line(center, to, 6);
    case 'ninja':
      for (var i = 0; i < 2; i++) {
        final side = i == 0 ? -1 : 1;
        line(to + Offset(-38 * s, side * 42 * s), to + Offset(38 * s * q, -side * 42 * s * q), 6);
      }
      line(from, center, 2);
    case 'magneto':
      for (var i = 0; i < 6; i++) {
        final angle = i * math.pi / 3 + t * 6;
        final point = Offset.lerp(to + Offset(math.cos(angle), math.sin(angle)) * 75 * s, from, q)!;
        c.drawRect(Rect.fromCenter(center: point, width: 8 * s, height: 12 * s), p..color = const Color(0xFFD5DEED)..style = PaintingStyle.fill);
        line(point, from, 1);
      }
      ring(to, 30 + 25 * math.sin(q * math.pi), squash: 1.5);
    case 'rocketeer':
    case 'goliath':
      for (var i = 0; i < (id == 'goliath' ? 1 : 3); i++) {
        final u = unit(q * 1.6 - i * .19);
        final point = Offset.lerp(from, to, u)! + Offset(0, -math.sin(u * math.pi) * (95 + i * 25) * s);
        line(point + Offset(-20 * s, 14 * s), point, id == 'goliath' ? 13 : 6, Colors.orangeAccent);
        orb(point, id == 'goliath' ? 15 : 8);
      }
    case 'scarab':
      for (var i = 0; i < 6; i++) {
        final angle = i * math.pi / 3 + t * 3;
        final point = from + Offset(math.cos(angle), math.sin(angle)) * (40 + q * 60) * s;
        final path = Path()..addPolygon([point + Offset(0, -13 * s), point + Offset(12 * s, 8 * s), point + Offset(-12 * s, 8 * s)], true);
        c.drawPath(path, p..color = color.withValues(alpha: .65)..style = PaintingStyle.fill);
      }
    case 'orbit':
      for (var i = 0; i < 3; i++) {
        c.save(); c.translate(center.dx, center.dy); c.rotate((i - 1) * .7 + t * 3);
        ring(Offset.zero, 40 + i * 12, squash: .32, width: 4); c.restore();
      }
    case 'guardian':
      final point = from + Offset(50 * s, 0);
      final path = Path()..addPolygon([point + Offset(-25 * s, -70 * s), point + Offset(25 * s, -70 * s), point + Offset(37 * s, 25 * s), point + Offset(0, 65 * s), point + Offset(-37 * s, 25 * s)], true);
      c.drawPath(path, p..color = color.withValues(alpha: .3 * strength)..style = PaintingStyle.fill);
      c.drawPath(path, p..color = color..style = PaintingStyle.stroke..strokeWidth = 4 * s);
      line(point, center, 8);
    case 'chronos':
      ring(to, 65, width: 3);
      for (var i = 0; i < 12; i++) { final angle = i * math.pi / 6; line(to + Offset(math.cos(angle), math.sin(angle)) * 54 * s, to + Offset(math.cos(angle), math.sin(angle)) * 62 * s, 2); }
      final angle = t < .3 ? t * 26 : 7.8;
      line(to, to + Offset(math.cos(angle), math.sin(angle)) * 45 * s, 4);
      line(to, to + Offset(math.cos(angle - 1.2), math.sin(angle - 1.2)) * 30 * s, 3);
      if (q > .3) ring(to, 80 * q, width: 1);
    case 'omega':
      for (final side in [-1, 1]) {
        final start = from + Offset(0, side * 35 * s);
        line(start, Offset.lerp(start, to, unit(q * 2))!, 11); line(start, to, 2, Colors.white);
      }
      ring(from, 45 + 20 * charge, squash: .6);
    case 'storm':
      for (var i = 0; i < (reduced ? 3 : 7); i++) {
        final point = to + Offset(math.sin(t * 20 + i) * (i + 2) * 7 * s, (i - 3) * 16 * s);
        ring(point, 12 + i * 7, squash: .28, width: 3);
        if (i.isEven && q > 0) arc(from, point, i, width: 2);
      }
    case 'chameleon':
      for (var i = 0; i < 8; i++) {
        final x = from.dx + (i - 3.5) * 13 * s;
        final y = from.dy + math.sin(i + t * 5) * 18 * s;
        c.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: Offset(x, y), width: 11 * s, height: 20 * s), Radius.circular(3 * s)), p..color = Color.lerp(color, Colors.cyanAccent, i / 8)!.withValues(alpha: .5 * strength)..style = PaintingStyle.fill);
      }
      line(to + Offset(0, -55 * s), to + Offset(0, 55 * s), 2); ring(from, 55 * q, squash: .65);
  }
}
