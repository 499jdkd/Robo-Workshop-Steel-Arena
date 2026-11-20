import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/game_motion.dart';
import 'package:flet_rive/src/robot/volt_motion.dart';

({GamePose pose, VoltFrame frame}) sample(
  String action,
  double t, {
  String weapon = '',
  double clock = 2,
}) {
  final p = GamePose(clock)..headY = -85;
  final frame = applyVoltPose(
    p,
    action,
    t,
    equippedWeapon: weapon,
    clock: clock,
  );
  return (pose: p, frame: frame);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'all Volt timelines stay finite and bounded, including invalid input',
    () {
      for (final action in [...voltActionSeconds.keys, 'idle', 'move']) {
        for (final t in [
          double.nan,
          double.infinity,
          -1.0,
          for (var i = 0; i <= 100; i++) i / 100,
          2.0,
        ]) {
          final result = sample(action, t);
          expect(
            result.pose.values.values.every((n) => n.isFinite),
            isTrue,
            reason: '$action at $t must be safe after pause/resume',
          );
          expect(result.pose.x.abs(), lessThan(85));
          expect(result.pose.y.abs(), lessThan(100));
          for (final intensity in [
            result.frame.coilGlow,
            result.frame.coreGlow,
            result.frame.charge,
            result.frame.discharge,
            result.frame.shield,
            result.frame.trail,
            result.frame.shockwave,
            result.frame.flash,
            result.frame.smoke,
            result.frame.sparks,
            result.frame.power,
          ]) {
            expect(intensity, inInclusiveRange(0, 1));
          }
        }
      }
    },
  );

  test('built-in electricity never deploys a universal weapon', () {
    for (final action in voltActionSeconds.keys) {
      final p = sample(action, .45).pose;
      expect(p.weapon, isEmpty, reason: action);
      expect(
        p.values['electric'],
        0,
        reason:
            'Electricity is emitted by articulated Tesla masts, not a gun mesh',
      );
      expect(p.deploy, 0);
      final equipped = sample(action, .45, weapon: 'sniper').pose;
      expect(equipped.weapon, 'sniper');
      expect(equipped.values['sniper'], 1);
      expect(equipped.deploy, greaterThan(.5));
    }
  });

  test(
    'attack, dash, coil charge and storm have distinct mechanical timing',
    () {
      final attack = sample('attack', .27);
      final quick = sample('quick', .3);
      final skill = sample('special', .38);
      final storm = sample('ultimate', .55);
      expect(attack.frame.discharge, greaterThan(.8));
      expect(quick.pose.x, greaterThan(35));
      expect(attack.pose.x, lessThan(0));
      expect(
        skill.frame.discharge,
        0,
        reason: 'Both masts must visibly charge before the skill releases',
      );
      expect(skill.pose.extra['joint0'], greaterThan(0));
      expect(skill.pose.extra['joint1'], lessThan(0));
      expect(storm.pose.extra['joint0'], lessThan(0));
      expect(storm.pose.extra['joint1'], greaterThan(0));
      expect(storm.pose.y, lessThan(-75));
      expect(sample('ultimate', .67).frame.discharge, greaterThan(.9));
      expect(sample('ultimate', .8).frame.shockwave, greaterThan(0));
      expect(sample('special', .55).frame.discharge, greaterThan(.9));
    },
  );

  test(
    'recovery connects the coils; electric guard and dodge remain distinct',
    () {
      final focus = sample('charge', .5);
      final guard = sample('guard', .5);
      final dodge = sample('dodge', .35);
      expect(focus.pose.extra['joint0'], greaterThan(.6));
      expect(focus.pose.extra['joint1'], lessThan(-.6));
      expect(focus.frame.charge, 1);
      expect(focus.frame.coreGlow, 1);
      expect(guard.frame.shield, 1);
      expect(
        guard.pose.shield,
        0,
        reason:
            'Volt uses his electric field instead of the common opaque shield',
      );
      expect(dodge.pose.x, lessThan(-50));
      expect(dodge.frame.trail, greaterThan(.9));
      expect(dodge.frame.shield, 0);
    },
  );

  test(
    'victory and defeat change individual parts, face and electrical power',
    () {
      final happy = sample('victory', .3);
      expect(happy.pose.armL, greaterThan(1.5));
      expect(happy.pose.armR, lessThan(-1.5));
      expect(happy.frame.sparks, greaterThan(.9));
      var lastPower = 1.0;
      for (var i = 0; i <= 100; i++) {
        final fail = sample('defeat', i / 100);
        expect(fail.frame.power, lessThanOrEqualTo(lastPower));
        lastPower = fail.frame.power;
      }
      final off = sample('defeat', 1);
      expect(off.frame.coilGlow, 0);
      expect(off.frame.coreGlow, 0);
      expect(off.frame.power, 0);
      expect(off.pose.sad, 1);
      expect(off.pose.eyeY, closeTo(.3, 1e-9));
      expect(off.pose.extra['jet'], closeTo(.12, 1e-9));
      expect(sample('defeat', .5).frame.smoke, greaterThan(.9));
    },
  );

  test(
    'touch reactions use different joints and return their root to rest',
    () {
      final fingerprints = <String>{};
      for (final action in [
        'joy',
        'jump',
        'surprise',
        'anger',
        'dance',
        'inspect',
      ]) {
        final p = sample(action, .35).pose;
        fingerprints.add(
          [
            p.y,
            p.body,
            p.head,
            p.armL,
            p.foreR,
            p.eyeY,
            p.brow,
            p.extra['joint0'],
          ].map((n) => n!.toStringAsFixed(4)).join(','),
        );
        final recovered = sample(action, 1).pose;
        expect(recovered.x, closeTo(0, 1e-8));
        expect(recovered.y, closeTo(0, 1e-8));
      }
      expect(fingerprints.length, 6);
      expect(
        sample('jump', .13).pose.y,
        greaterThan(0),
        reason: 'A jump begins by compressing its suspension',
      );
      expect(sample('jump', .5).pose.y, lessThan(-45));
      expect(sample('anger', .35).pose.brow, greaterThan(.4));
      expect(sample('surprise', .35).pose.shock, 1);
    },
  );

  test(
    'interrupted reactions blend the coil actuators and gaze moves the head',
    () {
      final previous = sample('ultimate', .5).pose;
      final next = sample('charge', .5).pose;
      final oldLeft = previous.extra['joint0']!;
      final newLeft = next.extra['joint0']!;
      blendVoltPose(next, previous, .5);
      expect(next.extra['joint0'], closeTo((oldLeft + newLeft) / 2, 1e-9));
      final beforeHead = next.head, beforeY = next.headY;
      voltTrackGaze(next, const Offset(12, -8));
      expect(next.head, closeTo(beforeHead + .24, 1e-9));
      expect(next.headY, closeTo(beforeY - 3.6, 1e-9));
    },
  );

  test('lightning anchors follow coil rotations, root rotation and facing', () {
    final p = GamePose(0);
    p.bodyY = 0;
    p.extra['joint0'] = p.extra['joint1'] = 0;
    const root = Offset(250, 300);
    final rest = voltAnchors(p, root, 1);
    expect(rest.leftCoil, const Offset(174, 185));
    expect(rest.rightCoil, const Offset(326, 185));
    p.extra['joint0'] = .5;
    final folded = voltAnchors(p, root, 1);
    expect(folded.leftCoil.dx, greaterThan(rest.leftCoil.dx));
    final mirrored = voltAnchors(p, root, 1, facing: -1);
    expect(
      mirrored.leftCoil.dx - root.dx,
      closeTo(root.dx - folded.leftCoil.dx, 1e-9),
    );
    expect(mirrored.leftCoil.dy, closeTo(folded.leftCoil.dy, 1e-9));
    p.rotation = .3;
    expect(voltAnchors(p, root, 1).leftCoil, isNot(folded.leftCoil));
  });

  test('new core rotor, iris and cooling actuators respond independently', () {
    final focused = sample('charge', .5).pose;
    expect(
      focused.extra['joint7'],
      closeTo(-focused.extra['joint4']! * .77, 1e-9),
    );
    expect(focused.extra['joint12'], lessThan(-.3));
    expect(focused.extra['joint13'], greaterThan(.3));
    final surprise = sample('surprise', .35).pose;
    final annoyed = sample('anger', .35).pose;
    expect(surprise.extra['joint10'], lessThan(annoyed.extra['joint10']!));
    expect(surprise.extra['joint11'], isNot(annoyed.extra['joint11']));
    final off = sample('defeat', 1).pose;
    expect(off.extra['joint12'], 0);
    expect(off.extra['joint13'], 0);
    expect(off.extra['joint10'], greaterThan(.6));
    for (final joint in [7, 10, 11, 12, 13]) {
      final next = sample('charge', .5).pose;
      final previous = sample('surprise', .35).pose;
      final expected =
          (next.extra['joint$joint']! + previous.extra['joint$joint']!) / 2;
      blendVoltPose(next, previous, .5);
      expect(next.extra['joint$joint'], closeTo(expected, 1e-9));
    }
  });

  test('audio cues cross once at the same moments at 30, 60 and 120 Hz', () {
    for (final action in voltCues.keys) {
      for (final hz in [30, 60, 120]) {
        var previous = -1e-6;
        final played = <String>[];
        final steps = (voltActionSeconds[action]! * hz).ceil();
        for (var i = 0; i <= steps; i++) {
          final now = i / steps;
          played.addAll(voltCuesCrossed(action, previous, now));
          previous = now;
        }
        expect(
          played,
          (voltCues[action]!).map((cue) => cue.name).toList(),
          reason: '$action at $hz Hz',
        );
        expect(voltCuesCrossed(action, 1, 1), isEmpty);
        expect(voltCuesCrossed(action, .6, .2), isEmpty);
      }
    }
  });

  Future<int> paintPixels(
    String action,
    double t, {
    bool reduced = false,
  }) async {
    final result = sample(action, t);
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    paintVoltEffects(
      canvas,
      result.frame,
      voltAnchors(result.pose, const Offset(110, 250), .7),
      const Offset(385, 130),
      285,
      .7,
      reduced: reduced,
    );
    final picture = recorder.endRecording();
    final image = await picture.toImage(500, 320);
    final pixels = (await image.toByteData(
      format: ui.ImageByteFormat.rawRgba,
    ))!;
    var nontransparent = 0;
    for (var i = 3; i < pixels.lengthInBytes; i += 4) {
      if (pixels.getUint8(i) > 0) nontransparent++;
    }
    image.dispose();
    picture.dispose();
    return nontransparent;
  }

  test(
    'native effects paint every action; reduced storm draws fewer pixels',
    () async {
      for (final action in [
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
        expect(
          await paintPixels(action, action == 'ultimate' ? .67 : .4),
          greaterThan(50),
          reason: '$action must have an actual visible electrical effect',
        );
      }
      final full = await paintPixels('ultimate', .67);
      final reduced = await paintPixels('ultimate', .67, reduced: true);
      expect(full, greaterThan(reduced));
      expect(reduced, greaterThan(200));
    },
  );
}
