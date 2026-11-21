import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/volt_energy.dart';
import 'volt_phone_readability_test.dart' as phone;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'shield keeps a moving luminous inner band with reduced effects',
    () async {
      final images = <ui.Image>[];
      final pixels = <ByteData>[];
      for (final t in [.25, .75]) {
        final recorder = ui.PictureRecorder();
        VoltEnergyPainter(
          Canvas(recorder),
          .5,
          t,
          reduced: true,
        ).shield(const Offset(100, 100), 1, 0, 1);
        final picture = recorder.endRecording();
        final image = await picture.toImage(200, 200);
        images.add(image);
        pixels.add(
          (await image.toByteData(format: ui.ImageByteFormat.rawRgba))!,
        );
        picture.dispose();
      }
      int bright(ByteData data, int x, int y) {
        final i = (y * 200 + x) * 4;
        return data.getUint8(i) > 150 &&
                data.getUint8(i + 1) > 210 &&
                data.getUint8(i + 2) > 210 &&
                data.getUint8(i + 3) > 150
            ? 1
            : 0;
      }

      var before = 0, after = 0, moved = 0;
      // This area excludes the bright rim. A transparent fill alone must fail.
      for (var y = 96; y < 132; y++) {
        for (var x = 60; x < 140; x++) {
          final a = bright(pixels[0], x, y), b = bright(pixels[1], x, y);
          before += a;
          after += b;
          if (a != b) moved++;
        }
      }
      expect(before, greaterThan(40));
      expect(after, greaterThan(40));
      expect(moved, greaterThan(60));
      for (final image in images) image.dispose();
    },
  );

  test(
    'skill and shield phases render on the real phone workshop backdrop',
    () async {
      final codec = await ui.instantiateImageCodec(
        File('../../src/assets/art/workshop-future-v1.png').readAsBytesSync(),
      );
      final backdrop = (await codec.getNextFrame()).image;
      final samples = <(String, double)>[
        ('special', .36),
        ('special', .55),
        ('special', .8),
        ('guard', .3),
        ('guard', .56),
        ('guard', .73),
      ];
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      canvas.scale(2);
      for (var i = 0; i < samples.length; i++) {
        canvas.save();
        canvas.translate((i % 3) * 320, (i ~/ 3) * 230);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        final scene = phone.sceneAt(samples[i].$1, samples[i].$2);
        phone.paintPhone(canvas, scene, backdrop: backdrop);
        scene.dispose();
        canvas.restore();
      }
      final picture = recorder.endRecording(),
          image = await picture.toImage(1920, 920);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      final out = Directory('../../.cache/volt-skill-shield-v39/review')
        ..createSync(recursive: true);
      File(
        '${out.path}/skill-shield-sequence.png',
      ).writeAsBytesSync(png.buffer.asUint8List());
      image.dispose();
      picture.dispose();
      backdrop.dispose();
      codec.dispose();
    },
  );
  test(
    'approved ultimate and other untouched actions keep their v38 pixels',
    () async {
      final samples = <(String, double)>[
        for (final action in [
          'attack',
          'quick',
          'dodge',
          'charge',
          'dance',
          'joy',
          'victory',
          'defeat',
          'inspect',
        ])
          for (final t in [.25, .55, .91]) (action, t),
        for (final t in [.14, .35, .52, .61, .71, .91]) ('ultimate', t),
      ];
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      for (var i = 0; i < samples.length; i++) {
        canvas.save();
        canvas.translate((i % 6) * 320, (i ~/ 6) * 230);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        final scene = phone.sceneAt(samples[i].$1, samples[i].$2);
        phone.paintPhone(canvas, scene);
        scene.dispose();
        canvas.restore();
      }
      final picture = recorder.endRecording(),
          actual = await picture.toImage(1920, 1380);
      final file = File('test/fixtures/volt-protected-v38.png');
      if (const bool.fromEnvironment('VOLT_CAPTURE_BASELINE')) {
        file.parent.createSync(recursive: true);
        final png = (await actual.toByteData(format: ui.ImageByteFormat.png))!;
        file.writeAsBytesSync(png.buffer.asUint8List());
      } else {
        final codec = await ui.instantiateImageCodec(file.readAsBytesSync());
        final expected = (await codec.getNextFrame()).image;
        final a = (await actual.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        final b = (await expected.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        expect(a.lengthInBytes, b.lengthInBytes);
        var differences = 0;
        for (var i = 0; i < a.lengthInBytes; i++) {
          if (a.getUint8(i) != b.getUint8(i)) differences++;
        }
        expect(
          differences,
          0,
          reason: 'Only skill and shield were requested to change',
        );
        expected.dispose();
        codec.dispose();
      }
      actual.dispose();
      picture.dispose();
    },
  );
}
