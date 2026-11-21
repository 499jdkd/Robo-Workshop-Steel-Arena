import 'dart:math' as math;
import 'package:flet/flet.dart';
import 'package:material_ui/material_ui.dart';

/// Presentation only: inventory is committed by Python before receipt changes.
class GameFactoryControl extends StatefulWidget {
  const GameFactoryControl({super.key, required this.control});
  final Control control;
  @override
  State<GameFactoryControl> createState() => _GameFactoryControlState();
}

class _GameFactoryControlState extends State<GameFactoryControl>
    with SingleTickerProviderStateMixin {
  late final AnimationController motor = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 12),
  )..repeat();
  final watch = Stopwatch();
  String receipt = '';
  @override
  Widget build(BuildContext context) {
    final next = widget.control.getString('receipt', '')!;
    if (next != receipt) {
      receipt = next;
      watch
        ..reset()
        ..start();
    }
    return LayoutControl(
      control: widget.control,
      child: SizedBox(
        height: widget.control.getDouble('height', 230),
        width: double.infinity,
        child: RepaintBoundary(
          child: AnimatedBuilder(
            animation: motor,
            builder: (context, _) => CustomPaint(
              painter: _FactoryPainter(
                motor.value * 12,
                receipt.isEmpty ? -1 : watch.elapsedMilliseconds / 1000,
                widget.control.getString('container_type', 'normal')!,
              ),
              size: Size.infinite,
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    motor.dispose();
    watch.stop();
    super.dispose();
  }
}

class _FactoryPainter extends CustomPainter {
  _FactoryPainter(this.clock, this.age, this.kind);
  final double clock, age;
  final String kind;
  double ease(double x) {
    x = x.clamp(0.0, 1.0);
    return x * x * (3 - 2 * x);
  }

  @override
  void paint(Canvas c, Size size) {
    c.save();
    c.scale(size.width / 400, size.height / 230);
    final p = Paint()..strokeCap = StrokeCap.round;
    c.drawRRect(
      RRect.fromRectAndRadius(
        const Rect.fromLTWH(0, 0, 400, 230),
        const Radius.circular(12),
      ),
      p
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF102545), Color(0xFF071A2F)],
        ).createShader(const Rect.fromLTWH(0, 0, 400, 230)),
    );
    p.shader = null;
    void line(Offset a, Offset b, Color col, double w) {
      c.drawLine(
        a,
        b,
        p
          ..color = col
          ..strokeWidth = w
          ..style = PaintingStyle.stroke,
      );
      p.style = PaintingStyle.fill;
    }

    void box(Rect r, List<Color> colors, double radius) {
      c.drawRRect(
        RRect.fromRectAndRadius(r, Radius.circular(radius)),
        p
          ..shader = LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: colors,
          ).createShader(r),
      );
      p.shader = null;
    }

    void poly(List<Offset> points, Color color) {
      final path = Path()..addPolygon(points, true);
      c.drawPath(path, p..color = color);
    }

    void gear(double x, double y, int teeth, double direction) {
      c.save();
      c.translate(x, y);
      c.rotate(clock * direction);
      for (var i = 0; i < teeth; i++) {
        c.save();
        c.rotate(i * math.pi * 2 / teeth);
        c.drawRRect(
          RRect.fromRectAndRadius(
            const Rect.fromLTWH(-3, -24, 6, 13),
            const Radius.circular(2),
          ),
          p..color = const Color(0xFF6886AA),
        );
        c.restore();
      }
      c.drawCircle(Offset.zero, 16, p..color = const Color(0xFF49617F));
      c.drawCircle(Offset.zero, 8, p..color = const Color(0xFF8DE7FB));
      c.restore();
    }

    for (final side in [-1, 1]) {
      final x = 200 + side * 150.0;
      box(Rect.fromLTWH(x - 16, 25, 32, 154), [
        const Color(0xFF607FA5),
        const Color(0xFF1F385B),
      ], 6);
      for (var i = 0; i < 4; i++)
        line(
          Offset(x - 11, 53 + i * 25.0),
          Offset(x + 11, 53 + i * 25.0),
          const Color(0xFF63D5ED),
          3,
        );
      gear(x, 38, 9, side * .6);
      final reach = 14 * ease(age / .5);
      line(
        Offset(x, 102),
        Offset(x - side * (40 + reach), 81),
        const Color(0xFFE9B657),
        13,
      );
      line(
        Offset(x - side * (40 + reach), 81),
        Offset(x - side * 65, 114),
        const Color(0xFF8AA9C6),
        9,
      );
    }
    c.drawOval(
      const Rect.fromLTWH(72, 172, 256, 45),
      p..color = const Color(0xFF172F4B),
    );
    c.drawOval(
      const Rect.fromLTWH(82, 169, 236, 34),
      p
        ..color = const Color(0xFF52DBF4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4,
    );
    p.style = PaintingStyle.fill;
    c.drawOval(
      const Rect.fromLTWH(87, 174, 226, 23),
      p..color = const Color(0xFF263F62),
    );
    final opening = age >= 0;
    final anticipation = opening
        ? math.sin(age * 32) * math.max(0, 1 - age / 1.2) * 3
        : math.sin(clock * 2) * 1.5;
    c.save();
    c.translate(anticipation, 0);
    final unlock = opening ? ease((age - .5) / .6) : 0.0;
    final rise = opening ? ease((age - 1.05) / .85) : 0.0;
    if (kind == 'capsule') {
      final egg = Path()..moveTo(200, 78 - rise * 40)
        ..cubicTo(145, 78 - rise * 40, 132, 177, 200, 185)
        ..cubicTo(268, 177, 255, 78 - rise * 40, 200, 78 - rise * 40)..close();
      c.drawPath(egg, p..shader = const LinearGradient(colors: [Color(0xFFE0C8FF), Color(0xFF6740A8)])
        .createShader(const Rect.fromLTWH(145, 70, 110, 120)));
      p.shader = null;
      c.drawOval(Rect.fromCenter(center: const Offset(200, 134), width: 105 + unlock * 22, height: 20),
        p..color = const Color(0xFFB9FFF1)..style = PaintingStyle.stroke..strokeWidth = 5);
      p.style = PaintingStyle.fill;
      c.drawCircle(const Offset(200, 122), 17, p..color = const Color(0xFF79E8FF));
    } else {
    c.save();
    if (kind == 'weapon') { c.translate(-42, 17); c.scale(1.2, .9); }
    if (kind == 'parts') { c.translate(20, -8); c.scale(.9, 1.05); }
    if (kind == 'rare') poly([
      const Offset(125, 110), const Offset(157, 74), const Offset(258, 74),
      const Offset(290, 110), const Offset(276, 181), const Offset(140, 181),
    ], const Color(0xFFE9B64E));
    box(const Rect.fromLTWH(136, 104, 128, 77), [
      const Color(0xFF9ABAD9),
      const Color(0xFF355579),
    ], 9);
    poly([
      const Offset(264, 104),
      const Offset(282, 91),
      const Offset(282, 167),
      const Offset(264, 181),
    ], const Color(0xFF294262));
    box(const Rect.fromLTWH(145, 116, 110, 53), [
      const Color(0xFF335687),
      const Color(0xFF182C50),
    ], 5);
    for (final side in [-1, 1])
      box(Rect.fromLTWH(194 + side * (36 + unlock * 18), 116, 12, 50), [
        const Color(0xFFF8D477),
        const Color(0xFF9C6D2D),
      ], 3);
    box(Rect.fromLTWH(185 - unlock * 40, 128, 30, 24), [
      const Color(0xFFD7F9FF),
      const Color(0xFF5688AB),
    ], 4);
    c.drawCircle(
      Offset(200 - unlock * 40, 140),
      5,
      p..color = const Color(0xFF6DF5FF),
    );
    if (kind == 'weapon') {
      for (var i = 0; i < 4; i++) {
        box(Rect.fromLTWH(158 + i * 22.0, 116, 12, 38), [const Color(0xFFE6BB70), const Color(0xFF986B39)], 4);
        poly([Offset(158 + i * 22.0, 116), Offset(164 + i * 22.0, 108), Offset(170 + i * 22.0, 116)], const Color(0xFF86DDF5));
      }
    }
    if (kind == 'parts') {
      c.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(176, 72, 48, 25), const Radius.circular(8)),
        p..color = const Color(0xFFE9BA73)..style = PaintingStyle.stroke..strokeWidth = 8);
      p.style = PaintingStyle.fill;
      gear(230, 141, 8, .15);
      box(const Rect.fromLTWH(145, 147, 34, 22), [const Color(0xFFE9BA73), const Color(0xFFA76B39)], 3);
    }
    if (kind == 'normal') {
      c.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(188, 125, 25, 19), const Radius.circular(5)), p..color = const Color(0xFFE1F6FF));
      c.drawCircle(const Offset(195, 133), 3, p..color = const Color(0xFF267CAB));
      c.drawCircle(const Offset(206, 133), 3, p..color = const Color(0xFF267CAB));
    }
    if (kind == 'rare') poly([const Offset(200, 114), const Offset(216, 134), const Offset(200, 158), const Offset(184, 134)], const Color(0xFFF5D579));
    c.save();
    c.translate(0, -rise * 68);
    poly([
      const Offset(136, 104),
      const Offset(158, 87),
      const Offset(282, 87),
      const Offset(264, 104),
    ], const Color(0xFFB6D3ED));
    box(const Rect.fromLTWH(136, 94, 129, 16), [
      const Color(0xFF8BDFF4),
      const Color(0xFF3B698C),
    ], 4);
    c.restore();
    c.restore();
    }
    c.restore();
    if (opening && rise > 0) {
      final origin = Offset(200, 119 - rise * 33);
      c.drawCircle(
        origin,
        70 + rise * 12,
        p
          ..shader = RadialGradient(
            colors: [
              Color.fromRGBO(136, 220, 255, .6 * rise),
              const Color(0x0046BFFF),
            ],
          ).createShader(Rect.fromCircle(center: origin, radius: 83)),
      );
      p.shader = null;
      for (var i = 0; i < 24; i++) {
        final t = (age - 1.1 - i * .018).clamp(0.0, 2.2);
        final a = i * 2.399;
        final pos =
            origin +
            Offset(math.cos(a) * t * 39, math.sin(a) * t * 34 - t * 25);
        c.drawCircle(
          pos,
          2.2,
          p
            ..color = Color.fromRGBO(
              168,
              238,
              255,
              (1 - t / 2.2).clamp(0.0, 1.0),
            ),
        );
      }
      if (age > 1.6) {
        final text = TextPainter(
          text: const TextSpan(
            text: 'НАГРАДЫ ПОЛУЧЕНЫ',
            style: TextStyle(
              color: Color(0xFFE4F8FF),
              fontSize: 13,
              fontWeight: FontWeight.w800,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout(maxWidth: 240);
        text.paint(c, Offset(200 - text.width / 2, 208));
      }
    }
    c.restore();
  }

  @override
  bool shouldRepaint(covariant _FactoryPainter old) =>
      old.clock != clock || old.age != age || old.kind != kind;
}
