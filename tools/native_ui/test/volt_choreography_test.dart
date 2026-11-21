import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';
import 'package:flet_rive/src/robot/volt_model.dart';
import 'package:flet_rive/src/robot/volt_geometry.dart';
import 'package:flet_rive/src/robot/volt_choreography.dart';

const actions = [
  'attack',
  'special',
  'ultimate',
  'guard',
  'quick',
  'dodge',
  'charge',
  'dance',
  'victory',
  'defeat',
];
({GamePose pose, VoltFrame frame}) poseAt(
  String action,
  double t, {
  double? hit,
}) {
  final pose = GamePose(0)
    ..headY = -85
    ..head = 0
    ..bodyY = 0;
  final frame = applyVoltPose(
    pose,
    action,
    t,
    clock: t * (voltActionSeconds[action] ?? 1),
    guardImpact: hit,
  );
  pose.extra['voltPower'] = frame.coilGlow;
  pose.extra['voltCore'] = frame.coreGlow;
  return (pose: pose, frame: frame);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final font = FontLoader('UI');
    font.addFont(
      Future.value(
        ByteData.sublistView(
          File('C:/Windows/Fonts/segoeui.ttf').readAsBytesSync(),
        ),
      ),
    );
    await font.load();
  });
  test(
    'all ten actions articulate limbs, face and suspension within physical bounds',
    () {
      for (final action in actions) {
        final varied = <String>{};
        final previous = <String, double>{};
        for (var i = 0; i <= 120; i++) {
          final p = poseAt(action, i / 120).pose;
          expect(p.x.abs(), lessThan(80), reason: action);
          expect(p.y.abs(), lessThan(100), reason: action);
          expect(p.extra.values.every((n) => n.isFinite), isTrue);
          for (final key in voltMechanismDefaults.keys) {
            final value = p.extra[key]!;
            if (previous.containsKey(key) &&
                (value - previous[key]!).abs() > .001)
              varied.add(key);
            previous[key] = value;
          }
          expect(p.extra['bodyscaleY'], inInclusiveRange(.97, 1.01));
          expect(p.extra['voltStrutL'], inInclusiveRange(.35, 1.5));
          expect(p.extra['voltStrutR'], inInclusiveRange(.35, 1.5));
        }
        expect(
          varied.length,
          greaterThanOrEqualTo(8),
          reason: '$action must move actual mechanisms',
        );
        final end = poseAt(action, 1).pose;
        if (action != 'defeat') {
          expect(end.x, closeTo(0, 1e-8), reason: action);
          expect(end.y, closeTo(0, 1e-8), reason: action);
          expect(end.armL, closeTo(.1, 1e-8));
          expect(end.armR, closeTo(-.1, 1e-8));
        }
      }
    },
  );
  test(
    'impulse, dash, skill, guard and storm have readable distinct silhouettes',
    () {
      final pulse = poseAt('attack', .29),
          dash = poseAt('quick', .29),
          skill = poseAt('special', .4),
          guard = poseAt('guard', .4),
          storm = poseAt('ultimate', .67);
      expect(pulse.pose.body, lessThan(-.15));
      expect(dash.pose.body, greaterThan(.3));
      expect(dash.pose.x, greaterThan(55));
      expect(pulse.pose.x, lessThan(0));
      expect(
        (dash.pose.extra['voltLegLY']! - dash.pose.extra['voltLegRY']!).abs(),
        greaterThan(10),
      );
      expect(skill.pose.armL, greaterThan(1.5));
      expect(guard.pose.foreR, greaterThan(1));
      expect(storm.pose.armL, greaterThan(2));
      expect(storm.pose.y, lessThan(-65));
      expect(poseAt('ultimate', .5).frame.energyField, greaterThan(.5));
      expect(poseAt('ultimate', .67).frame.camera, greaterThan(.4));
      expect(poseAt('attack', .15).frame.discharge, 0);
      expect(poseAt('special', .35).frame.discharge, 0);
    },
  );
  test(
    'jump compresses suspension first, tucks it in flight and settles after landing',
    () {
      final down = poseAt('jump', .14).pose,
          up = poseAt('jump', .37).pose,
          land = poseAt('jump', .8).pose,
          settle = poseAt('jump', .91).pose;
      expect(down.y, greaterThan(10));
      expect(down.extra['voltLegLY'], lessThan(70));
      expect(down.extra['bodyscaleY'], lessThan(.98));
      expect(up.y, lessThan(-50));
      expect(up.armL, greaterThan(1));
      expect(up.extra['joint14'], greaterThan(.2));
      expect(land.y, greaterThan(5));
      expect(settle.y, lessThan(0));
      expect(land.head, isNot(settle.head));
      expect(land.extra['joint0'], isNot(settle.extra['joint0']));
    },
  );
  test(
    'shield hits deform posture and gain energy without changing combat state',
    () {
      final quiet = poseAt('guard', .6, hit: 0),
          hit = poseAt('guard', .6, hit: 1);
      expect(hit.frame.shieldHit, 1);
      expect(quiet.frame.shieldHit, 0);
      expect(hit.pose.x, lessThan(quiet.pose.x - 5));
      expect(hit.pose.body, lessThan(quiet.pose.body));
      expect(hit.frame.coilGlow, greaterThanOrEqualTo(quiet.frame.coilGlow));
      expect(quiet.frame.shield, hit.frame.shield);
    },
  );
  test(
    'new suspension and screen channels are bound to real authored nodes',
    () {
      for (final key in voltMechanismDefaults.keys) {
        expect(
          voltGeometryNodes.any(
            (n) => [
              n.xBinding,
              n.yBinding,
              n.rotationBinding,
              n.scaleXBinding,
              n.scaleYBinding,
            ].contains(key),
          ),
          isTrue,
          reason: key,
        );
      }
    },
  );
  test(
    'interruptions blend every new mechanical channel and electrical intensity',
    () {
      final before = poseAt('ultimate', .55), after = poseAt('guard', .4);
      final oldLeg = before.pose.extra['voltLegLY']!,
          newLeg = after.pose.extra['voltLegLY']!;
      blendVoltPose(after.pose, before.pose, .5);
      expect(
        after.pose.extra['voltLegLY'],
        closeTo((oldLeg + newLeg) / 2, 1e-8),
      );
      final frame = blendVoltFrame(after.frame, before.frame, .5);
      expect(
        frame.charge,
        closeTo((before.frame.charge + after.frame.charge) / 2, 1e-8),
      );
      expect(voltBlendSeconds('quick'), lessThan(.1));
    },
  );
  test(
    'shutdown holds until new input and randomized reactions never repeat in a bag',
    () {
      final scene = GameSceneClock(reactionSeed: 71)
        ..viewport = const Size(844, 390);
      scene.update({
        'robot': 'volt',
        'arena': false,
        'demonstration': true,
        'expanded': true,
        'sound': false,
        'phase': 'workshop',
        'event': 'start',
        'action': 'idle',
      });
      scene.advance(0);
      scene.showcase('defeat');
      scene.advance(3.1);
      expect(scene.playerVoltFrame!.power, 0);
      scene.advance(10);
      expect(scene.playerVoltFrame!.power, 0);
      final offHead = scene.player.pose.head, offY = scene.player.pose.y;
      scene.pointAt(const Offset(820, 20));
      scene.advance(.5);
      expect(scene.player.pose.head, offHead);
      expect(scene.player.pose.y, offY);
      final groups = <List<String>>[];
      String? last;
      for (var bag = 0; bag < 4; bag++) {
        final reactions = <String>[];
        for (var n = 0; n < 7; n++) {
          scene.react();
          expect(scene.localAction, isNot(last));
          last = scene.localAction;
          reactions.add(last!);
          scene.advance(voltActionSeconds[last]! + 1);
        }
        expect(reactions.toSet().length, 7);
        groups.add(reactions);
      }
      expect(groups.map((g) => g.join(',')).toSet().length, greaterThan(1));
      scene.dispose();
    },
  );
  test(
    'workshop reward echoes do not replace the native shuffled reaction',
    () {
      final scene = GameSceneClock(reactionSeed: 71)
        ..viewport = const Size(390, 294);
      scene.update({
        'robot': 'volt',
        'arena': false,
        'sound': false,
        'action': 'idle',
        'combatAction': 'idle',
        'event': '0',
      });
      scene.advance(0);
      scene.react();
      scene.advance(1.7);
      scene.react();
      final chosen = scene.localAction;
      expect(chosen, isNot('joy'));
      scene.advance(.1);
      scene.update({
        ...scene.data,
        'action': 'joy',
        'combatAction': 'joy',
        'event': '1',
      });
      scene.advance(0);
      expect(scene.localAction, chosen);
      expect(scene.playerVoltFrame!.action, chosen);
      scene.dispose();
    },
  );
  test(
    'short impulse settles to Volt idle before the generic weapon timeline ends',
    () {
      GameSceneClock scene() {
        final value = GameSceneClock()..viewport = const Size(844, 390);
        value.update({
          'robot': 'volt',
          'arena': false,
          'demonstration': true,
          'expanded': true,
          'sound': false,
          'phase': 'workshop',
          'event': 'start',
          'action': 'idle',
        });
        value.advance(0);
        return value;
      }

      final attacked = scene(), resting = scene();
      attacked.showcase('attack');
      attacked.advance(.3);
      attacked.advance(.7);
      attacked.advance(.2);
      resting.advance(1.2);
      expect(attacked.playerVoltFrame!.action, 'idle');
      final actual = attacked.player.pose, expected = resting.player.pose;
      expect(actual.armL, closeTo(expected.armL, 1e-8));
      expect(actual.armR, closeTo(expected.armR, 1e-8));
      expect(actual.foreR, closeTo(expected.foreR, 1e-8));
      expect(actual.body, closeTo(expected.body, 1e-8));
      expect(actual.mode, expected.mode);
      attacked.dispose();
      resting.dispose();
    },
  );
  test(
    'reactor recovery takes the short angular path after a long session',
    () {
      final before = poseAt('ultimate', .5).pose,
          after = poseAt('defeat', 1).pose;
      before.extra['joint4'] = 100;
      before.extra['joint7'] = -77;
      blendVoltPose(after, before, .5);
      expect((after.extra['joint4']! - 100).abs(), lessThan(1.58));
      expect((after.extra['joint7']! + 77).abs(), lessThan(1.58));
    },
  );
  void paintCell(Canvas canvas, String action, double t) {
    const scale = .58;
    final sample = poseAt(action, t), p = sample.pose;
    canvas.drawColor(const Color(0xFF10233F), BlendMode.src);
    final origin = Offset(106 + p.x * scale, 150 + p.y * scale);
    canvas.drawLine(
      const Offset(0, 239),
      const Offset(220, 239),
      Paint()
        ..color = const Color(0xFF39607A)
        ..strokeWidth = 1,
    );
    drawVoltModel(canvas, p, origin, scale, 1);
    paintVoltEffects(
      canvas,
      sample.frame,
      voltAnchors(p, origin, scale),
      const Offset(206, 130),
      239,
      scale,
    );
    final label = TextPainter(
      text: TextSpan(
        text: '$action  ${(t * 100).round()}%',
        style: const TextStyle(
          fontFamily: 'UI',
          color: Colors.white,
          fontSize: 12,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    label.paint(canvas, const Offset(5, 5));
  }

  test(
    'native review sheets show preparation, release and recovery for all actions',
    () async {
      final out = Directory('../../.cache/volt-motion-v36/renders')
        ..createSync(recursive: true);
      const phases = [0.0, .15, .32, .5, .68, .9, 1.0];
      for (var sheet = 0; sheet < 2; sheet++) {
        final recorder = ui.PictureRecorder();
        // Use one native recording per sheet; never modify screenshots afterwards.
        final c = Canvas(recorder);
        for (var row = 0; row < 5; row++) {
          for (var column = 0; column < phases.length; column++) {
            c.save();
            c.translate(column * 220, row * 250);
            c.clipRect(const Rect.fromLTWH(0, 0, 220, 250));
            paintCell(c, actions[sheet * 5 + row], phases[column]);
            c.restore();
          }
        }
        final picture = recorder.endRecording(),
            image = await picture.toImage(1540, 1250);
        final bytes = (await image.toByteData(format: ui.ImageByteFormat.png))!;
        File(
          '${out.path}/sheet-$sheet.png',
        ).writeAsBytesSync(bytes.buffer.asUint8List());
        image.dispose();
        picture.dispose();
      }
      if (const bool.fromEnvironment('VOLT_REVIEW_FRAMES')) {
        final frames = Directory('${out.path}/frames')..createSync();
        var index = 0;
        for (final action in actions) {
          final count = (voltActionSeconds[action]! * 30).ceil();
          for (var frame = 0; frame <= count; frame++) {
            final recorder = ui.PictureRecorder();
            final c = Canvas(recorder);
            c.scale(2);
            paintCell(c, action, frame / count);
            final picture = recorder.endRecording(),
                image = await picture.toImage(440, 500);
            final png = (await image.toByteData(
              format: ui.ImageByteFormat.png,
            ))!;
            File(
              '${frames.path}/${index.toString().padLeft(5, '0')}.png',
            ).writeAsBytesSync(png.buffer.asUint8List());
            image.dispose();
            picture.dispose();
            index++;
          }
        }
      }
    },
    timeout: const Timeout(Duration(minutes: 2)),
  );
}
