import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/volt_model.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';

GameSceneClock sceneAt(String action, double t, {bool reduced = false}) {
  final scene = GameSceneClock()..viewport = const Size(320, 230);
  scene.update({
    'robot': 'volt',
    'arena': false,
    'demonstration': true,
    'expanded': false,
    'sound': false,
    'reducedEffects': reduced,
    'action': 'idle',
    'combatAction': 'idle',
    'event': 'phone-review',
    'phase': 'workshop',
  });
  scene.advance(0);
  scene.showcase(action);
  scene.advance(0);
  scene.advance(voltActionSeconds[action]! * t);
  return scene;
}

void paintPhone(
  Canvas canvas,
  GameSceneClock scene, {
  bool effectsOnly = false,
  ui.Image? backdrop,
}) {
  final s = scene.scale, p = scene.player.pose, frame = scene.playerVoltFrame!;
  final origin = Offset(scene.player.center, scene.floor + (p.y - 126) * s);
  if (!effectsOnly) {
    canvas.drawColor(const Color(0xFF10233F), BlendMode.src);
    if (backdrop != null) {
      paintImage(
        canvas: canvas,
        rect: const Rect.fromLTWH(0, 0, 320, 230),
        image: backdrop,
        fit: BoxFit.cover,
      );
    }
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(scene.player.center, scene.floor),
        width: 135 * s,
        height: 15 * s,
      ),
      Paint()..color = const Color(0xFF193654),
    );
    paintVoltMotionEchoes(canvas, frame, origin, s, reduced: scene.reduced);
    drawVoltModel(canvas, p, origin, s, scene.player.facing);
  }
  paintVoltEffects(
    canvas,
    frame,
    voltAnchors(p, origin, s),
    Offset(320 * .87, scene.floor - 130 * s),
    scene.floor,
    s,
    preview: true,
    reduced: scene.reduced,
  );
}

Future<ui.Image> imageAt(
  String action,
  double t, {
  bool effectsOnly = false,
  bool reduced = false,
}) async {
  final scene = sceneAt(action, t, reduced: reduced);
  final recorder = ui.PictureRecorder();
  paintPhone(Canvas(recorder), scene, effectsOnly: effectsOnly);
  final picture = recorder.endRecording(),
      image = await picture.toImage(320, 230);
  picture.dispose();
  scene.dispose();
  return image;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final font = FontLoader('UI')
      ..addFont(
        Future.value(
          ByteData.sublistView(
            File('C:/Windows/Fonts/segoeui.ttf').readAsBytesSync(),
          ),
        ),
      );
    await font.load();
  });

  test(
    'phone skill beam occupies a wide channel while the impulse remains compact',
    () async {
      Future<int> brightPixels(String action) async {
        final image = await imageAt(action, .75, effectsOnly: true);
        final data = (await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        var count = 0;
        for (var y = 30; y < 160; y++) {
          for (var x = 195; x < 285; x++) {
            final i = (y * 320 + x) * 4;
            if (data.getUint8(i + 3) > 120 &&
                data.getUint8(i + 1) > 180 &&
                data.getUint8(i + 2) > 180)
              count++;
          }
        }
        image.dispose();
        return count;
      }

      final pulse = await brightPixels('attack'),
          beam = await brightPixels('special');
      expect(beam, greaterThan(180));
      expect(
        beam,
        greaterThan(pulse * 2),
        reason: 'A sustained skill must read differently at 320 logical pixels',
      );
    },
  );

  test(
    'reduced effects retain the charged orb, pulse and shield silhouette',
    () async {
      for (final action in ['attack', 'special', 'ultimate', 'guard']) {
        final image = await imageAt(
          action,
          action == 'ultimate' ? .55 : .5,
          effectsOnly: true,
          reduced: true,
        );
        final data = (await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        var visible = 0;
        for (var i = 3; i < data.lengthInBytes; i += 4)
          if (data.getUint8(i) > 100) visible++;
        expect(visible, greaterThan(80), reason: action);
        image.dispose();
      }
    },
  );

  test(
    'phone review captures use real scene positions and bounds for six actions',
    () async {
      const actions = [
        'attack',
        'quick',
        'special',
        'guard',
        'dodge',
        'ultimate',
      ];
      const phases = [.15, .36, .55, .73, .91];
      final out = Directory('../../.cache/volt-readability-v37/phone')
        ..createSync(recursive: true);
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      for (var row = 0; row < actions.length; row++) {
        for (var col = 0; col < phases.length; col++) {
          canvas.save();
          canvas.translate(col * 320, row * 230);
          canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
          final scene = sceneAt(actions[row], phases[col]);
          paintPhone(canvas, scene);
          scene.dispose();
          final label = TextPainter(
            text: TextSpan(
              text: '${actions[row]} ${(100 * phases[col]).round()}%',
              style: const TextStyle(
                fontFamily: 'UI',
                fontSize: 11,
                color: Colors.white,
              ),
            ),
            textDirection: TextDirection.ltr,
          )..layout();
          label.paint(canvas, const Offset(6, 213));
          canvas.restore();
        }
      }
      final picture = recorder.endRecording(),
          image = await picture.toImage(1600, 1380);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      File(
        '${out.path}/phone-actions.png',
      ).writeAsBytesSync(png.buffer.asUint8List());
      image.dispose();
      picture.dispose();
    },
  );
  test(
    'effects remain readable over the actual bright workshop artwork',
    () async {
      final codec = await ui.instantiateImageCodec(
        File('../../src/assets/art/workshop-future-v1.png').readAsBytesSync(),
      );
      final backdrop = (await codec.getNextFrame()).image;
      const actions = [
        'attack',
        'quick',
        'special',
        'guard',
        'dodge',
        'ultimate',
      ];
      const phases = [.4, .36, .78, .56, .36, .55];
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      for (var i = 0; i < actions.length; i++) {
        canvas.save();
        canvas.translate((i % 3) * 320, (i ~/ 3) * 230);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        final scene = sceneAt(actions[i], phases[i]);
        paintPhone(canvas, scene, backdrop: backdrop);
        scene.dispose();
        final text = TextPainter(
          text: TextSpan(
            text: actions[i],
            style: const TextStyle(
              fontFamily: 'UI',
              fontSize: 12,
              color: Colors.white,
              backgroundColor: Color(0xD010233F),
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        text.paint(canvas, const Offset(6, 211));
        canvas.restore();
      }
      final picture = recorder.endRecording(),
          image = await picture.toImage(960, 460);
      final data = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      final out = Directory('../../.cache/volt-readability-v37/phone')
        ..createSync(recursive: true);
      File(
        '${out.path}/workshop-effects.png',
      ).writeAsBytesSync(data.buffer.asUint8List());
      image.dispose();
      picture.dispose();
      backdrop.dispose();
      codec.dispose();
    },
  );
}
