import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_geometry.dart';
import 'package:flet_rive/src/robot/volt_model.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';

GamePose poseFor(String action, double t, {String weapon = ''}) {
  final pose = GamePose(0)
    ..headY = -85
    ..head = 0
    ..bodyY = 0
    ..body = 0;
  final frame = applyVoltPose(
    pose,
    action,
    t,
    clock: 1.7,
    equippedWeapon: weapon,
  );
  pose.extra['voltPower'] = frame.coilGlow;
  pose.extra['voltCore'] = frame.coreGlow;
  return pose;
}

ui.Picture recordModel(
  GamePose pose, {
  required bool cached,
  Color accent = const Color(0xFF36DFFF),
  double scale = 1,
  double facing = 1,
  Offset gaze = Offset.zero,
}) {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  canvas.drawColor(const Color(0xFF10233F), BlendMode.src);
  drawVoltModel(
    canvas,
    pose,
    const Offset(280, 370),
    scale,
    facing,
    accent: accent,
    gaze: gaze,
    cacheStaticAssemblies: cached,
  );
  return recorder.endRecording();
}

Future<ByteData> renderPixels(
  GamePose pose, {
  required bool cached,
  Color accent = const Color(0xFF36DFFF),
  double scale = 1,
  double facing = 1,
  Offset gaze = Offset.zero,
}) async {
  final picture = recordModel(
    pose,
    cached: cached,
    accent: accent,
    scale: scale,
    facing: facing,
    gaze: gaze,
  );
  final image = await picture.toImage(560, 620);
  final pixels = (await image.toByteData(format: ui.ImageByteFormat.rawRgba))!;
  image.dispose();
  picture.dispose();
  return pixels;
}

double percentile(List<double> samples, double fraction) {
  final sorted = List<double>.from(samples)..sort();
  return sorted[((sorted.length - 1) * fraction).round()];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(clearVoltModelCaches);
  tearDown(clearVoltModelCaches);

  test(
    'immutable assemblies preserve pixel output through live poses and skins',
    () async {
      for (final action in [
        'idle',
        'attack',
        'quick',
        'special',
        'guard',
        'dodge',
        'charge',
        'ultimate',
        'victory',
        'defeat',
      ]) {
        final pose = poseFor(action, action == 'defeat' ? .82 : .48);
        final reference = await renderPixels(pose, cached: false);
        final optimized = await renderPixels(pose, cached: true);
        var error = 0, changed = 0;
        for (var i = 0; i < reference.lengthInBytes; i++) {
          final difference = (reference.getUint8(i) - optimized.getUint8(i))
              .abs();
          error += difference;
          if (difference > 3) changed++;
        }
        expect(
          error / reference.lengthInBytes,
          lessThan(.05),
          reason: '$action must preserve vector colors, gradients and opacity',
        );
        expect(
          changed / reference.lengthInBytes,
          lessThan(.001),
          reason: '$action must not change part order or antialiasing',
        );
      }
      for (final weapon in ['', 'sniper', 'rocket', 'sword']) {
        final pose = poseFor('attack', .32, weapon: weapon);
        const accent = Color(0xFFFFB43B);
        final reference = await renderPixels(
          pose,
          cached: false,
          accent: accent,
          facing: -1,
          scale: .83,
          gaze: const Offset(4, -3),
        );
        final optimized = await renderPixels(
          pose,
          cached: true,
          accent: accent,
          facing: -1,
          scale: .83,
          gaze: const Offset(4, -3),
        );
        var error = 0;
        for (var i = 0; i < reference.lengthInBytes; i++) {
          error += (reference.getUint8(i) - optimized.getUint8(i)).abs();
        }
        expect(
          error / reference.lengthInBytes,
          lessThan(.05),
          reason: '$weapon must preserve mirroring, skin and weapon deployment',
        );
      }
    },
  );

  test(
    'partial opacity retains per-path blending instead of composite group opacity',
    () async {
      final pose = poseFor('defeat', .67)
        ..extra['voltPower'] = .43
        ..extra['voltCore'] = .31;
      final reference = await renderPixels(pose, cached: false);
      final optimized = await renderPixels(pose, cached: true);
      var maxDifference = 0;
      for (var i = 0; i < reference.lengthInBytes; i++) {
        final difference = (reference.getUint8(i) - optimized.getUint8(i))
            .abs();
        if (difference > maxDifference) maxDifference = difference;
      }
      expect(maxDifference, lessThanOrEqualTo(3));
    },
  );

  test(
    'joints, gaze, core and weapon remain independent of cached assemblies',
    () async {
      final resting = poseFor('idle', 0);
      final moved = poseFor('idle', 0)
        ..extra['joint0'] = .7
        ..extra['joint1'] = -.6
        ..extra['joint4'] = 1.1
        ..head = .27;
      final a = await renderPixels(resting, cached: true);
      final b = await renderPixels(
        moved,
        cached: true,
        gaze: const Offset(4, -3),
      );
      var changed = 0;
      for (var i = 0; i < a.lengthInBytes; i += 4) {
        if ((a.getUint8(i + 1) - b.getUint8(i + 1)).abs() > 15) changed++;
      }
      expect(
        changed,
        greaterThan(1000),
        reason:
            'Caching must not replace the articulated character with a whole-robot image',
      );
      final armed = poseFor('attack', .36, weapon: 'sniper');
      final expected = await renderPixels(armed, cached: false);
      final actual = await renderPixels(armed, cached: true);
      var error = 0;
      for (var i = 0; i < expected.lengthInBytes; i++) {
        error += (expected.getUint8(i) - actual.getUint8(i)).abs();
      }
      expect(error / expected.lengthInBytes, lessThan(.05));
    },
  );

  test(
    'warm assemblies are reused through poses, zoom and mirror without new recordings',
    () {
      warmVoltModel();
      final warmed = Map<String, int>.from(voltModelCacheStats);
      expect(warmed['sourceShapes'], voltGeometryShapeCount);
      expect(warmed['staticShapes'], greaterThan(40));
      expect(warmed['staticShapes'], lessThan(voltGeometryShapeCount));
      expect(warmed['staticAssemblies'], greaterThan(4));
      for (var i = 0; i < 30; i++) {
        final picture = recordModel(
          poseFor('special', i / 30),
          cached: true,
          scale: .7 + i / 80,
          facing: i.isEven ? -1 : 1,
        );
        picture.dispose();
      }
      expect(voltModelCacheStats, warmed);
    },
  );

  test(
    'accent churn and explicit eviction respect native picture and material limits',
    () {
      for (var i = 0; i < 40; i++) {
        warmVoltModel(
          accent: Color.fromARGB(255, i * 5, 210 - i * 3, 100 + i * 3),
        );
        final stats = voltModelCacheStats;
        expect(
          stats['accentVariants'],
          lessThanOrEqualTo(stats['maxAccentVariants']!),
        );
        expect(
          stats['pictureAccentVariants'],
          lessThanOrEqualTo(stats['maxAccentVariants']!),
        );
        expect(
          stats['assemblyPictures'],
          lessThanOrEqualTo(
            stats['maxAccentVariants']! * stats['maxAssembliesPerAccent']!,
          ),
        );
        expect(
          stats['pictureBytes'],
          lessThanOrEqualTo(stats['pictureBudgetBytes']!),
        );
      }
      final paths = voltModelCacheStats['paths'];
      clearVoltModelCaches();
      expect(voltModelCacheStats['pictureBytes'], 0);
      expect(voltModelCacheStats['assemblyPictures'], 0);
      expect(voltModelCacheStats['accentVariants'], 0);
      expect(voltModelCacheStats['paths'], paths);
      warmVoltModel();
      final picture = recordModel(poseFor('idle', 0), cached: true);
      picture.dispose();
      expect(voltModelCacheStats['assemblyPictures'], greaterThan(0));
    },
  );

  test(
    'warming an existing accent refreshes its material and Picture LRU entry',
    () {
      const active = Color(0xFF36DFFF);
      warmVoltModel(accent: active);
      for (var i = 0; i < 7; i++) {
        warmVoltModel(accent: Color.fromARGB(255, 20 + i, 80, 110));
      }
      warmVoltModel(accent: active);
      warmVoltModel(accent: const Color(0xFFFA1234));
      final recordings = voltModelCacheStats['recordedAssemblies'];
      warmVoltModel(accent: active);
      expect(
        voltModelCacheStats['recordedAssemblies'],
        recordings,
        reason: 'The most recently warmed skin must survive accent eviction',
      );
    },
  );

  test('invalid surface coordinates are rejected before Canvas commands', () {
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final pose = poseFor('idle', 0);
    drawVoltModel(canvas, pose, const Offset(10, 20), double.nan, 1);
    drawVoltModel(canvas, pose, const Offset(double.infinity, 20), 1, 1);
    drawVoltModel(canvas, pose, const Offset(10, 20), -1, 1);
    recorder.endRecording().dispose();
    expect(voltModelCacheStats['assemblyPictures'], 0);
  });

  test(
    'native recording benchmark reports CPU work without claiming Android FPS',
    () async {
      final warm = Stopwatch()..start();
      warmVoltModel();
      warm.stop();
      final poses = [for (var i = 0; i < 60; i++) poseFor('special', i / 60)];
      for (var i = 0; i < 80; i++) {
        recordModel(poses[i % poses.length], cached: i.isEven).dispose();
      }
      final raw = <double>[], cached = <double>[];
      for (var i = 0; i < 360; i++) {
        // Alternate ordering to reduce JIT/thermal drift between the samples.
        for (final cache in i.isEven ? [false, true] : [true, false]) {
          final stopwatch = Stopwatch()..start();
          final picture = recordModel(poses[i % poses.length], cached: cache);
          stopwatch.stop();
          (cache ? cached : raw).add(stopwatch.elapsedMicroseconds / 1000);
          picture.dispose();
        }
      }
      final report = {
        'measurement':
            'Native Flutter test engine; Dart/Canvas command recording CPU only. No Android execution or FPS claim.',
        'samples_per_mode': raw.length,
        'warm_ms': warm.elapsedMicroseconds / 1000,
        'uncached_recording_ms': {
          'p50': percentile(raw, .5),
          'p95': percentile(raw, .95),
        },
        'assembly_picture_recording_ms': {
          'p50': percentile(cached, .5),
          'p95': percentile(cached, .95),
        },
        'cache': voltModelCacheStats,
        'gpu_raster_improvement_verified': false,
      };
      final out = Directory('../../.cache/volt-motion-v36/cache')
        ..createSync(recursive: true);
      File(
        '${out.path}/native-recording-benchmark.json',
      ).writeAsStringSync(const JsonEncoder.withIndent('  ').convert(report));
      print(jsonEncode(report));
      // A timing report is evidence, not a brittle wall-clock pass threshold.
      expect(raw.length, 360);
      expect(cached.length, 360);
    },
  );
}
