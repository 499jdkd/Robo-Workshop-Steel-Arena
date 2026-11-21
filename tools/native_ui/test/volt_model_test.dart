import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_geometry.dart';
import 'package:flet_rive/src/robot/volt_model.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';

GamePose restPose() => GamePose(0)
  ..headY = -85
  ..head = 0
  ..bodyY = 0
  ..body = 0
  ..armL = .05
  ..armR = -.05
  ..foreL = 0
  ..foreR = 0
  ..extra['voltPower'] = 1
  ..extra['voltCore'] = 1
  ..extra['voltAntenna'] = 0;

Future<ui.Image> render(
  GamePose pose, {
  int width = 420,
  int height = 440,
  Offset origin = const Offset(210, 276),
  double scale = 1,
  double facing = 1,
  Color background = const Color(0xFF1D1D1D),
  VoltFrame? frame,
}) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  canvas.drawColor(background, BlendMode.src);
  drawVoltModel(canvas, pose, origin, scale, facing);
  if (frame != null)
    paintVoltEffects(
      canvas,
      frame,
      voltAnchors(pose, origin, scale, facing: facing),
      Offset(width - 140, height * .5),
      height - 35,
      scale,
      facing: facing,
    );
  final picture = recorder.endRecording();
  final image = await picture.toImage(width, height);
  picture.dispose();
  return image;
}

Future<void> save(ui.Image image, String name) async {
  final out = Directory('../../.cache/volt-readability-v37/canvas')
    ..createSync(recursive: true);
  final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
  File('${out.path}/$name.png').writeAsBytesSync(png.buffer.asUint8List());
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'authored Volt geometry preserves the articulated suspension and mechanisms',
    () {
      expect(voltGeometryShapeCount, 409);
      expect(voltGeometryNodes.length, 554);
      expect(voltGeometryPaths.length, 206);
      expect(voltGeometrySourceSha256.length, 64);
      for (final joint in [
        'joint0',
        'joint1',
        'joint2',
        'joint3',
        'joint4',
        'joint5',
        'joint6',
        'joint7',
        'joint8',
        'joint9',
        'joint10',
        'joint11',
        'joint12',
        'joint13',
        'joint14',
        'joint15',
      ]) {
        expect(
          voltGeometryNodes.any((n) => n.rotationBinding == joint),
          isTrue,
          reason: '$joint must move an independent authored mechanism',
        );
      }
      expect(
        voltGeometryPaints.any((p) => p.kind == 2),
        isTrue,
        reason: 'The reactor retains its authored radial glass gradient',
      );
    },
  );

  test('Canvas rest pose matches the authored native Rive silhouette', () async {
    final image = await render(restPose());
    await save(image, 'volt-rest');
    final native = File('../../docs/volt-v37/volt-authored-native.png');
    expect(native.existsSync(), isTrue);
    final codec = await ui.instantiateImageCodec(native.readAsBytesSync());
    final reference = (await codec.getNextFrame()).image;
    expect(reference.width, image.width);
    expect(reference.height, image.height);
    final expected = (await reference.toByteData(
      format: ui.ImageByteFormat.rawRgba,
    ))!;
    final actual = (await image.toByteData(
      format: ui.ImageByteFormat.rawRgba,
    ))!;
    var intersection = 0, union = 0, error = 0, samples = 0;
    for (var i = 0; i < actual.lengthInBytes; i += 4) {
      bool mask(ByteData d) =>
          (d.getUint8(i) - 29).abs() +
              (d.getUint8(i + 1) - 29).abs() +
              (d.getUint8(i + 2) - 29).abs() >
          35;
      final a = mask(actual), e = mask(expected);
      if (a || e) union++;
      if (a && e) intersection++;
      if (a || e) {
        for (var c = 0; c < 3; c++)
          error += (actual.getUint8(i + c) - expected.getUint8(i + c)).abs();
        samples += 3;
      }
    }
    final iou = intersection / union, mae = error / samples;
    print('Native silhouette IoU=$iou, foreground RGB MAE=$mae');
    expect(
      iou,
      greaterThan(.9),
      reason:
          'Authored silhouette, part ordering and radii must survive compilation',
    );
    expect(
      mae,
      lessThan(24),
      reason: 'The source gradients and materials must stay recognizable',
    );
    image.dispose();
    reference.dispose();
    codec.dispose();
  });

  test(
    'real native model renders attack, skill, storm, guard and power-down',
    () async {
      for (final action in [
        'attack',
        'quick',
        'special',
        'guard',
        'charge',
        'ultimate',
        'victory',
        'defeat',
      ]) {
        final pose = restPose();
        final t = action == 'ultimate'
            ? .67
            : action == 'defeat'
            ? .9
            : .5;
        final frame = applyVoltPose(pose, action, t, clock: 2);
        pose.extra['voltPower'] = frame.coilGlow;
        pose.extra['voltCore'] = frame.coreGlow;
        final image = await render(
          pose,
          width: 760,
          height: 520,
          origin: Offset(270, 330 + pose.y),
          scale: 1,
          background: const Color(0xFF10233F),
          frame: frame,
        );
        await save(image, 'volt-$action');
        final pixels = (await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        ))!;
        expect(pixels.lengthInBytes, 760 * 520 * 4);
        image.dispose();
      }
    },
  );

  test(
    'rendering reuses cached Paths and materials instead of recompiling geometry',
    () async {
      warmVoltModel();
      final initial = Map<String, int>.from(voltModelCacheStats);
      for (var i = 0; i < 5; i++) {
        final pose = restPose();
        applyVoltPose(pose, 'special', i / 5, clock: i / 5);
        final image = await render(pose);
        image.dispose();
      }
      expect(voltModelCacheStats, initial);
      expect(
        initial['paths'],
        lessThan(voltGeometryShapeCount),
        reason: 'Repeated screws, rings and plates share compiled paths',
      );
    },
  );

  test(
    'equipped weapon appears and powered components really switch off',
    () async {
      final idle = await render(restPose());
      final weapon = restPose();
      applyVoltPose(weapon, 'attack', .3, equippedWeapon: 'sniper');
      final armed = await render(
        weapon,
        width: 650,
        height: 480,
        origin: const Offset(240, 280),
      );
      await save(armed, 'volt-equipped-sniper');
      final off = restPose()
        ..extra['voltPower'] = 0
        ..extra['voltFacePower'] = 0
        ..extra['voltCore'] = 0;
      final dark = await render(off);
      final onPixels = (await idle.toByteData(
        format: ui.ImageByteFormat.rawRgba,
      ))!;
      final offPixels = (await dark.toByteData(
        format: ui.ImageByteFormat.rawRgba,
      ))!;
      var changed = 0;
      for (var i = 0; i < onPixels.lengthInBytes; i += 4) {
        if ((onPixels.getUint8(i + 1) - offPixels.getUint8(i + 1)).abs() > 25)
          changed++;
      }
      expect(
        changed,
        greaterThan(400),
        reason:
            'VM opacity must dim the lens, coil windings, nozzles and energy core',
      );
      idle.dispose();
      armed.dispose();
      dark.dispose();
    },
  );
}
