import 'dart:io';
import 'dart:convert';
import 'dart:ui' as ui;
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/titan_motion.dart';
import 'package:flet_rive/src/robot/titan_model.dart';
import 'package:flet_rive/src/robot/titan_geometry.dart';
import 'package:flet_rive/src/robot/scene_audio.dart';

GameSceneClock titanScene(String action, double t, {bool reduced = false}) {
  final scene = GameSceneClock()..viewport = const Size(320, 230);
  scene.update({
    'robot': 'titan',
    'arena': false,
    'demonstration': true,
    'sound': false,
    'reducedEffects': reduced,
    'action': 'idle',
    'combatAction': 'idle',
    'event': 'review',
    'phase': 'workshop',
  });
  scene.advance(0);
  scene.showcase(action);
  scene.advance(0);
  scene.advance((titanActionSeconds[action] ?? 1) * t);
  return scene;
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
    'all eighteen Titan timelines move independent real parts and stay finite',
    () {
      expect(titanActionSeconds.length, 18);
      for (final action in titanActionSeconds.keys) {
        final changed = <String>{};
        Map<String, double>? before;
        for (var i = 0; i <= 120; i++) {
          final pose = GamePose(0);
          final frame = applyTitanPose(pose, action, i / 120, clock: i / 60);
          expect(pose.x.abs(), lessThan(130), reason: action);
          expect(pose.y.abs(), lessThan(80), reason: action);
          expect(
            pose.extra.values.every((v) => v.isFinite),
            true,
            reason: action,
          );
          expect(frame.power, inInclusiveRange(0, 1));
          final channels = <String, double>{
            ...pose.extra,
            'head': pose.head,
            'headY': pose.headY,
            'body': pose.body,
            'bodyY': pose.bodyY,
            'armL': pose.armL,
            'armR': pose.armR,
            'foreL': pose.foreL,
            'foreR': pose.foreR,
            'x': pose.x,
            'y': pose.y,
          };
          if (before != null)
            for (final key in channels.keys) {
              if ((channels[key]! - (before[key] ?? 0)).abs() > .0001)
                changed.add(key);
            }
          before = Map.of(channels);
          expect(
            pose.weapon,
            isEmpty,
            reason: 'Built-in pile drivers must not deploy a stock gun',
          );
        }
        expect(changed.length, greaterThanOrEqualTo(9), reason: action);
      }
      expect(titanGeometryShapeCount, greaterThan(350));
      for (final channel in [
        'titanHammerL',
        'titanHammerR',
        'titanPistonL',
        'titanLegYL',
        'titanVentL',
      ]) {
        expect(
          titanGeometryNodes.any(
            (n) =>
                [n.xBinding, n.yBinding, n.rotationBinding].contains(channel),
          ),
          true,
          reason: channel,
        );
      }
    },
  );
  test(
    'Titan sound milestones cross exactly once at different refresh rates',
    () {
      for (final action in titanActionSeconds.keys) {
        final expected = (titanCues[action] ?? []).map((c) => c.name).toList();
        for (final hz in [30, 60, 120]) {
          final seen = <String>[];
          var before = -.001;
          for (var i = 0; i <= hz; i++) {
            seen.addAll(titanCuesCrossed(action, before, i / hz));
            before = i / hz;
          }
          expect(seen, expected, reason: '$action at $hz Hz');
          expect(seen.every(SceneAudio.cueSeconds.containsKey), true);
        }
      }
    },
  );
  test(
    'Titan workshop reactions do not repeat; floor travel and pause use local clock',
    () {
      final scene = titanScene('inspect', 1);
      final reactions = <String>{};
      for (var i = 0; i < 7; i++) {
        scene.advance(3);
        scene.react();
        reactions.add(scene.localAction);
        scene.advance(.2);
      }
      expect(reactions.length, 7);
      scene.advance(3);
      scene.react();
      scene.advance(.1);
      scene.react();
      scene.advance(.1);
      scene.react();
      expect(scene.localAction, 'anger');
      scene.advance(3);
      final from = scene.player.center;
      scene.moveTo(const Offset(90, 215));
      scene.advance(.7);
      expect((scene.player.center - from).abs(), greaterThan(10));
      final clock = scene.clock;
      scene.suspended = true;
      scene.advance(10);
      expect(scene.clock, clock);
      scene.dispose();
    },
  );
  test(
    'Titan shutdown reaches zero power and remains off across UI updates',
    () {
      final scene = titanScene('defeat', 1);
      expect(scene.playerVoltFrame!.power, 0);
      expect(scene.player.pose.extra['titanPower'], 0);
      final head = scene.player.pose.head;
      scene.advance(3);
      expect(scene.player.pose.head, head);
      expect(scene.player.pose.extra['titanPower'], 0);
      expect(scene.player.pose.sad, 1);
      scene.dispose();
    },
  );
  test('native Titan owns both arena roles and retains equipped modules', () {
    for (final enemy in [false, true]) {
      for (final action in [
        'attack',
        'quick',
        'special',
        'ultimate',
        'guard',
        'dodge',
        'charge',
      ]) {
        final scene = GameSceneClock()..viewport = const Size(844, 390);
        scene.update({
          'robot': enemy ? 'volt' : 'titan',
          'enemy': enemy ? 'titan' : 'volt',
          'arena': true,
          'sound': false,
          'action': action,
          'combatAction': action,
          'enemyCombatAction': action,
          'phase': enemy ? 'enemy-flight' : 'approach',
          'progress': .4,
          'prepareSeconds': .55,
          'event': '$enemy-$action',
          'equipped': ['laser'],
          'enemyEquipped': ['laser'],
          'weapon': 'laser',
          'enemyWeapon': 'laser',
        });
        scene.advance(0);
        scene.advance(.3);
        final frame = enemy ? scene.enemyVoltFrame : scene.playerVoltFrame;
        final actor = enemy ? scene.enemy : scene.player;
        expect(frame, isNotNull);
        expect(actor.pose.extra.containsKey('titanHammerL'), true);
        expect(actor.pose.weapon, 'laser');
        expect(actor.pose.deploy, greaterThan(0));
        scene.dispose();
      }
    }
  });
  test('Titan reuses bounded part textures and releases them on pressure', () {
    clearTitanModelCaches();
    warmTitanModel();
    final warm = titanModelCacheStats;
    expect(warm['rasterAssemblies'], greaterThan(0));
    expect(warm['rasterBytes'], lessThanOrEqualTo(warm['rasterBudgetBytes']!));
    for (var i = 0; i < 120; i++) {
      final scene = titanScene('ultimate', i / 120);
      final recorder = ui.PictureRecorder();
      GameEffectsPainter(scene).paint(Canvas(recorder), const Size(320, 230));
      recorder.endRecording().dispose();
      scene.dispose();
    }
    expect(titanModelCacheStats['rasterizations'], warm['rasterizations']);
    for (var i = 0; i < 12; i++) {
      warmTitanModel(accent: Color(0xFF204060 + i * 0x030507));
      final stats = titanModelCacheStats;
      expect(
        stats['rasterBytes'],
        lessThanOrEqualTo(stats['rasterBudgetBytes']!),
      );
      expect(
        stats['pictureBytes'],
        lessThanOrEqualTo(stats['pictureBudgetBytes']!),
      );
      expect(stats['accentVariants'], lessThanOrEqualTo(8));
    }
    clearTitanModelCaches();
    expect(titanModelCacheStats['rasterBytes'], 0);
    expect(titanModelCacheStats['rasterAssemblies'], 0);
    expect(titanModelCacheStats['pictureBytes'], 0);
  });
  test(
    'Titan part textures retain vector silhouettes and fine detail',
    () async {
      final report = <String, double>{};
      for (final sample in <(String, double)>[
        ('inspect', .05),
        ('attack', .64),
        ('guard', .55),
        ('ultimate', .65),
        ('defeat', .85),
      ]) {
        final scene = titanScene(sample.$1, sample.$2);
        final pose = scene.player.pose;
        Future<ui.Image> render(bool cached) async {
          final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
          canvas.scale(3);
          drawTitanModel(
            canvas,
            pose,
            const Offset(160, 180),
            .62,
            1,
            cacheStaticAssemblies: cached,
          );
          final picture = recorder.endRecording();
          final image = await picture.toImage(960, 690);
          picture.dispose();
          return image;
        }

        final vector = await render(false), cached = await render(true);
        final a = (await vector.toByteData())!.buffer.asUint8List();
        final b = (await cached.toByteData())!.buffer.asUint8List();
        var count = 0, error = 0, silhouetteDifference = 0;
        for (var i = 0; i < a.length; i += 4) {
          if (a[i + 3] > 10 || b[i + 3] > 10) {
            count++;
            for (var c = 0; c < 4; c++) error += (a[i + c] - b[i + c]).abs();
            if ((a[i + 3] > 127) != (b[i + 3] > 127)) silhouetteDifference++;
          }
        }
        expect(count, greaterThan(10000));
        final meanError = error / (count * 4);
        report[sample.$1] = meanError;
        expect(meanError, lessThan(1), reason: sample.$1);
        expect(silhouetteDifference / count, lessThan(.01), reason: sample.$1);
        vector.dispose();
        cached.dispose();
        scene.dispose();
      }
      File(
        '../../.cache/titan-v40/raster-quality.json',
      ).writeAsStringSync(jsonEncode(report));
    },
  );
  test(
    'Titan native review shows different action silhouettes and real phone bounds',
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
        'charge',
        'ultimate',
        'victory',
        'defeat',
        'dance',
        'jump',
        'surprise',
      ];
      const phases = [.14, .35, .55, .73, .93];
      final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
      for (var row = 0; row < actions.length; row++) {
        for (var col = 0; col < phases.length; col++) {
          canvas.save();
          canvas.translate(col * 320, row * 230);
          canvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
          paintImage(
            canvas: canvas,
            rect: const Rect.fromLTWH(0, 0, 320, 230),
            image: backdrop,
            fit: BoxFit.cover,
          );
          final scene = titanScene(actions[row], phases[col]);
          GameEffectsPainter(scene).paint(canvas, const Size(320, 230));
          final label = TextPainter(
            text: TextSpan(
              text: '${actions[row]} ${(phases[col] * 100).round()}%',
              style: const TextStyle(
                fontFamily: 'UI',
                fontSize: 11,
                color: Colors.white,
                backgroundColor: Color(0xDD10233F),
              ),
            ),
            textDirection: TextDirection.ltr,
          )..layout();
          label.paint(canvas, const Offset(6, 212));
          scene.dispose();
          canvas.restore();
        }
      }
      final picture = recorder.endRecording(),
          image = await picture.toImage(1600, 2760);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      final out = Directory('../../.cache/titan-v40/review')
        ..createSync(recursive: true);
      File(
        '${out.path}/all-actions.png',
      ).writeAsBytesSync(png.buffer.asUint8List());
      final focusRecorder = ui.PictureRecorder(),
          focusCanvas = Canvas(focusRecorder);
      focusCanvas.scale(2);
      final samples = <(String, double)>[
        ('inspect', .05),
        ('special', .93),
        ('guard', .55),
        ('ultimate', .55),
        ('ultimate', .66),
        ('ultimate', .95),
      ];
      for (var i = 0; i < samples.length; i++) {
        focusCanvas.save();
        focusCanvas.translate((i % 3) * 320, (i ~/ 3) * 230);
        focusCanvas.clipRect(const Rect.fromLTWH(0, 0, 320, 230));
        paintImage(
          canvas: focusCanvas,
          rect: const Rect.fromLTWH(0, 0, 320, 230),
          image: backdrop,
          fit: BoxFit.cover,
        );
        final scene = titanScene(samples[i].$1, samples[i].$2);
        GameEffectsPainter(scene).paint(focusCanvas, const Size(320, 230));
        scene.dispose();
        focusCanvas.restore();
      }
      final focusPicture = focusRecorder.endRecording(),
          focusImage = await focusPicture.toImage(1920, 920);
      final focusPng = (await focusImage.toByteData(
        format: ui.ImageByteFormat.png,
      ))!;
      File(
        '${out.path}/ability-sequence.png',
      ).writeAsBytesSync(focusPng.buffer.asUint8List());
      focusImage.dispose();
      focusPicture.dispose();
      image.dispose();
      picture.dispose();
      backdrop.dispose();
      codec.dispose();
      expect(titanModelCacheStats['paths'], greaterThan(150));
    },
  );
}
