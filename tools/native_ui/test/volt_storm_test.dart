import 'dart:io';
import 'dart:ui' as ui;
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';
import 'package:flet_rive/src/robot/volt_storm.dart';
import 'volt_phone_readability_test.dart' as phone;

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
    'ultimate sequence shows growth, pressure, release and impact on the real backdrop',
    () async {
      final codec = await ui.instantiateImageCodec(
        File('../../src/assets/art/workshop-future-v1.png').readAsBytesSync(),
      );
      final backdrop = (await codec.getNextFrame()).image;
      const phases = [.14, .35, .52, .61, .71, .91];
      const labels = [
        'Spark',
        'Gather',
        'Full charge',
        'Compression',
        'Discharge',
        'Impact',
      ];
      final out = Directory('../../.cache/volt-super-v38/storm')
        ..createSync(recursive: true);
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      for (var i = 0; i < phases.length; i++) {
        canvas.save();
        canvas.translate((i % 3) * 320, (i ~/ 3) * 230);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        final scene = phone.sceneAt('ultimate', phases[i]);
        phone.paintPhone(canvas, scene, backdrop: backdrop);
        scene.dispose();
        final label = TextPainter(
          text: TextSpan(
            text: labels[i],
            style: const TextStyle(
              fontFamily: 'UI',
              fontSize: 12,
              color: Colors.white,
              backgroundColor: Color(0xD010233F),
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        label.paint(canvas, const Offset(6, 211));
        canvas.restore();
      }
      final picture = recorder.endRecording(),
          image = await picture.toImage(960, 460);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      File(
        '${out.path}/sequence.png',
      ).writeAsBytesSync(png.buffer.asUint8List());
      image.dispose();
      picture.dispose();
      if (const bool.fromEnvironment('VOLT_STORM_VIDEO')) {
        final frames = Directory('${out.path}/frames')..createSync();
        for (var i = 0; i <= 78; i++) {
          final scene = phone.sceneAt('ultimate', (i / 30 / 2.55).clamp(0, 1));
          final recorder = ui.PictureRecorder();
          phone.paintPhone(Canvas(recorder), scene, backdrop: backdrop);
          scene.dispose();
          final picture = recorder.endRecording(),
              image = await picture.toImage(320, 230);
          final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
          File(
            '${frames.path}/${i.toString().padLeft(4, '0')}.png',
          ).writeAsBytesSync(png.buffer.asUint8List());
          image.dispose();
          picture.dispose();
        }
      }
      backdrop.dispose();
      codec.dispose();
    },
  );
  test(
    'storm grows from a small spark, compresses, then releases on the existing boundary',
    () {
      var last = 0.0;
      for (var i = 0; i <= 42; i++) {
        final phase = VoltStorm(.10 + i / 100);
        expect(phase.radius, greaterThanOrEqualTo(last));
        expect(phase.discharge, 0);
        last = phase.radius;
      }
      expect(VoltStorm(.12).radius, lessThan(9));
      expect(VoltStorm(.52).radius, closeTo(86, 1e-8));
      expect(VoltStorm(.61).radius, lessThan(74));
      expect(VoltStorm(.6).charge, 1);
      expect(VoltStorm(.62).discharge, 0);
      expect(VoltStorm(.67).discharge, 1);
      expect(VoltStorm(.72).extension, 1);
      expect(VoltStorm(.9).arrival, 1);
      for (final t in [double.nan, double.infinity, -2.0, 2.0]) {
        final phase = VoltStorm(t);
        expect(
          [
            phase.radius,
            phase.charge,
            phase.discharge,
            phase.pressure,
          ].every((v) => v.isFinite),
          isTrue,
        );
      }
    },
  );

  test(
    'held ultimate pose stores tension in the opened coils before recoil',
    () {
      GamePose pose(double t) {
        final p = GamePose(0)..headY = -85;
        applyVoltPose(p, 'ultimate', t, clock: 2);
        return p;
      }

      final hold = pose(.57), ready = pose(.61), fire = pose(.68);
      expect(hold.armL, ready.armL);
      expect(hold.y, ready.y);
      expect(hold.extra['joint0']!.abs(), greaterThan(.9));
      expect(hold.extra['voltEmitterTravel'], lessThan(-22));
      expect(fire.body, lessThan(hold.body - .2));
    },
  );

  test(
    'the complete large charge fits short portrait scenes and mirrors correctly',
    () {
      for (final size in [
        const Size(320, 230),
        const Size(390, 294),
        const Size(844, 280),
      ]) {
        for (final face in [-1.0, 1.0]) {
          final scene = phone.sceneAt('ultimate', .52)..viewport = size;
          scene.player.facing = face;
          scene.advance(0);
          final scale = scene.scale, pose = scene.player.pose;
          final origin = Offset(
            scene.player.center,
            scene.floor + (pose.y - 126) * scale,
          );
          final anchors = voltAnchors(pose, origin, scale, facing: face);
          final center = voltStormCenter(
            anchors,
            scene.playerVoltFrame!,
            scale,
            facing: face,
            viewport: Offset.zero & size,
          );
          final radius = VoltStorm.maximumRadius * 1.36 * scale;
          expect(center.dx - radius, greaterThan(4));
          expect(center.dy - radius, greaterThan(4));
          expect(center.dx + radius, lessThan(size.width - 4));
          expect(center.dy + radius, lessThan(size.height - 4));
          scene.dispose();
        }
      }
    },
  );

  test(
    'ultimate charge is visibly larger than the skill on a 320px phone',
    () async {
      Future<int> visible(String action, double t) async {
        final image = await phone.imageAt(action, t, effectsOnly: true);
        final data = (await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        var count = 0;
        for (var i = 3; i < data.lengthInBytes; i += 4)
          if (data.getUint8(i) > 150) count++;
        image.dispose();
        return count;
      }

      final skill = await visible('special', .4),
          storm = await visible('ultimate', .52);
      expect(storm, greaterThan(skill * 3));
    },
  );
  test('other Volt actions retain v39 pixels on Flutter 3.47', () async {
    const actions = [
      'attack',
      'quick',
      'special',
      'guard',
      'dodge',
      'charge',
      'dance',
      'joy',
      'victory',
      'defeat',
    ];
    const phases = [.25, .55, .91];
    final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
    for (var row = 0; row < phases.length; row++) {
      for (var col = 0; col < actions.length; col++) {
        canvas.save();
        canvas.translate(col * 320, row * 230);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        final scene = phone.sceneAt(actions[col], phases[row]);
        phone.paintPhone(canvas, scene);
        scene.dispose();
        canvas.restore();
      }
    }
    final picture = recorder.endRecording(),
        actual = await picture.toImage(3200, 690);
    final referenceFile = File('test/fixtures/volt-other-actions-v39-flutter347.png');
    if (const bool.fromEnvironment('VOLT_CAPTURE_BASELINE')) {
      referenceFile.parent.createSync(recursive: true);
      final png = (await actual.toByteData(format: ui.ImageByteFormat.png))!;
      referenceFile.writeAsBytesSync(png.buffer.asUint8List());
    } else {
      final codec = await ui.instantiateImageCodec(
        referenceFile.readAsBytesSync(),
      );
      final expected = (await codec.getNextFrame()).image;
      final a = (await actual.toByteData(format: ui.ImageByteFormat.rawRgba))!;
      final b = (await expected.toByteData(
        format: ui.ImageByteFormat.rawRgba,
      ))!;
      expect(a.lengthInBytes, b.lengthInBytes);
      var differences = 0;
      for (var i = 0; i < a.lengthInBytes; i++) {
        final x = (i ~/ 4) % 3200;
        // v39 explicitly improves the skill and shield (columns 2 and 3).
        // Their replacements have their own tests; all other columns stay fixed.
        if (x >= 640 && x < 1280) continue;
        if (a.getUint8(i) != b.getUint8(i)) differences++;
      }
      expect(
        differences,
        0,
        reason:
            'Changes outside the approved skill and shield are not expected',
      );
      expected.dispose();
      codec.dispose();
    }
    actual.dispose();
    picture.dispose();
  });
}
