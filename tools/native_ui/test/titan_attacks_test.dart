import 'dart:io';
import 'dart:ui' as ui;
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/titan_motion.dart';
import 'package:flet_rive/src/robot/titan_strikes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'four quick contacts alternate real fists; ordinary punch has one contact',
    () {
      const origin = Offset(180, 240), target = Offset(650, 210);
      for (var i = 0; i < titanQuickHits.length; i++) {
        final pose = GamePose(0);
        final frame = applyTitanPose(pose, 'quick', titanQuickHits[i]);
        final fists = titanFistStrikes(frame, pose, origin, target, .8, 1);
        expect(fists.length, 2);
        final active = fists.singleWhere((f) => f.left == i.isOdd);
        final other = fists.singleWhere((f) => f.left != i.isOdd);
        expect((active.tip - target).distance, lessThan(.001));
        expect((other.tip - target).distance, greaterThan(25));
        expect(fists.every((f) => !f.detached), true);
      }
      final pose = GamePose(0),
          frame = applyTitanPose(GamePose(0), 'attack', .9);
      applyTitanPose(pose, 'attack', .9);
      final fists = titanFistStrikes(frame, pose, origin, target, .8, 1);
      expect(fists.length, 1);
      expect(fists.single.left, false);
      expect((fists.single.tip - target).distance, lessThan(.001));
    },
  );
  test(
    'skill leaves one open wrist, hits its live target, and brings its gauntlet back',
    () {
      for (final facing in [-1.0, 1.0]) {
        final origin = Offset(facing > 0 ? 160 : 680, 250);
        final target = Offset(facing > 0 ? 680 : 160, 210);
        for (final t in [.2, .46, .63, titanSkillImpact, .9, .99, 1.0]) {
          final pose = GamePose(0);
          final frame = applyTitanPose(pose, 'special', t);
          final fists = titanFistStrikes(
            frame,
            pose,
            origin,
            target,
            .8,
            facing,
          );
          expect(
            frame.shockwave,
            0,
            reason: 'Skill must not repeat the seismic ultimate',
          );
          expect(
            pose.y,
            greaterThanOrEqualTo(0),
            reason: 'Skill does not jump or slam the ground',
          );
          if (t < titanSkillRelease || t == 1) {
            expect(fists, isEmpty);
            expect(pose.extra['titanExternalFistR'], 0);
          } else {
            expect(fists.length, 1);
            expect(fists.single.detached, true);
            expect(fists.single.left, false);
            expect(pose.extra['titanExternalFistL'], 0);
            if (t == titanSkillImpact)
              expect((fists.single.tip - target).distance, lessThan(.001));
            if (t == .99)
              expect(
                (fists.single.tip - titanFist(pose, origin, .8, facing, false))
                    .distance,
                lessThan(8),
              );
          }
        }
      }
    },
  );
  test(
    'seismic wave reaches close/far defenders in both directions and leaves the arena',
    () {
      for (final width in [320.0, 390.0, 844.0, 1200.0]) {
        for (final facing in [-1.0, 1.0]) {
          for (final close in [false, true]) {
            final ground = Offset(width * (facing > 0 ? .23 : .77), 250);
            final target = Offset(
              close
                  ? ground.dx + facing * 25
                  : width * (facing > 0 ? .83 : .17),
              150,
            );
            final viewport = Rect.fromLTWH(0, 0, width, 300);
            Offset sample(double t) => titanWaveFront(
              ground,
              target,
              250,
              .6,
              t,
              facing: facing,
              viewport: viewport,
            );
            expect((sample(.9).dx - target.dx).abs(), lessThan(.001));
            expect((sample(.95).dx - target.dx) * facing, greaterThan(0));
            expect(
              facing > 0
                  ? sample(1).dx > viewport.right
                  : sample(1).dx < viewport.left,
              true,
            );
            var previous = sample(.62).dx;
            for (var i = 1; i <= 100; i++) {
              final x = sample(.62 + .38 * i / 100).dx;
              expect((x - previous) * facing, greaterThanOrEqualTo(-.001));
              previous = x;
            }
          }
        }
      }
    },
  );
  test(
    'arena damage phases align skill contact and return for either actor',
    () {
      for (final opponent in [false, true]) {
        final scene = GameSceneClock()..viewport = const Size(844, 390);
        scene.update({
          'robot': opponent ? 'volt' : 'titan',
          'enemy': opponent ? 'titan' : 'volt',
          'arena': true,
          'sound': false,
          'reducedEffects': true,
          'combatAction': 'special',
          'enemyCombatAction': 'special',
          'action': 'special',
          'phase': opponent ? 'reply' : 'impact',
          'progress': 1,
          'event': 'skill-hit-$opponent',
        });
        scene.advance(0);
        final frame = opponent ? scene.enemyVoltFrame : scene.playerVoltFrame;
        expect(frame!.action, 'special');
        expect(frame.t, closeTo(titanSkillImpact, .001));
        scene.advance(.24);
        final recovery = opponent
            ? scene.enemyVoltFrame
            : scene.playerVoltFrame;
        expect(recovery!.t, greaterThan(.98));
        scene.dispose();
      }
    },
  );
  test(
    'arena flight advances both fist travel and the seismic front locally',
    () {
      for (final action in ['attack', 'quick', 'special', 'ultimate']) {
        final scene = GameSceneClock()..viewport = const Size(844, 390);
        scene.update({
          'robot': 'titan',
          'enemy': 'titan',
          'arena': true,
          'sound': false,
          'reducedEffects': true,
          'action': action,
          'combatAction': action,
          'phase': 'flight',
          'flightSeconds': .72,
          'event': 'local-$action',
        });
        scene.advance(0);
        final start = scene.playerVoltFrame!.t;
        scene.advance(.36);
        final middle = scene.playerVoltFrame!.t;
        final hit = action == 'special' ? titanSkillImpact : .9;
        expect(middle, closeTo((start + hit) / 2, .001));
        scene.advance(.36);
        expect(scene.playerVoltFrame!.t, closeTo(hit, .001));
        scene.dispose();
      }
    },
  );
  test('export real arena contacts and flying gauntlet sequence', () async {
    final recorder = ui.PictureRecorder(), canvas = Canvas(recorder);
    const phases = [.2, .36, .54, .63, .72, .78, .9, .96];
    const actions = ['attack', 'quick', 'special', 'ultimate'];
    for (var row = 0; row < actions.length; row++) {
      for (var col = 0; col < phases.length; col++) {
        final scene = GameSceneClock()..viewport = const Size(844, 390);
        final action = actions[row], t = phases[col];
        final release = action == 'special'
            ? .46
            : action == 'ultimate'
            ? .62
            : action == 'quick'
            ? .26
            : .22;
        final hit = action == 'special' ? titanSkillImpact : .9;
        final phase = t < release
            ? 'approach'
            : t < hit
            ? 'flight'
            : 'impact';
        scene.update({
          'robot': 'titan',
          'enemy': 'titan',
          'arena': true,
          'sound': false,
          'reducedEffects': true,
          'action': action,
          'combatAction': action,
          'phase': phase,
          'progress': ((t - release) / (hit - release)).clamp(0.0, 1.0),
          'prepareSeconds': 1.0,
          'impactSeconds': 1.0,
          'event': '$row-$col',
        });
        scene.advance(0);
        if (phase == 'approach') scene.advance(t / release);
        if (phase == 'flight')
          scene.advance(.72 * (t - release) / (hit - release));
        if (phase == 'impact') scene.advance((t - hit) / (1 - hit));
        canvas.save();
        canvas.translate(col * 422.0, row * 195.0);
        canvas.scale(.5);
        canvas.clipRect(const Rect.fromLTWH(0, 0, 844, 390));
        canvas.drawColor(const Color(0xFF283848), BlendMode.src);
        GameEffectsPainter(scene).paint(canvas, const Size(844, 390));
        canvas.restore();
        scene.dispose();
      }
    }
    final picture = recorder.endRecording(),
        image = await picture.toImage(3376, 780);
    final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
    final out = Directory('../../.cache/titan-v43/review')
      ..createSync(recursive: true);
    File(
      '${out.path}/arena-attacks.png',
    ).writeAsBytesSync(png.buffer.asUint8List());
    image.dispose();
    picture.dispose();
  });
}
