import 'package:flet_rive/flet_rive.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/robot_profiles.dart';

GameSceneClock scene() => GameSceneClock()
  ..update({
    'arena': false,
    'phase': 'workshop',
    'action': 'idle',
    'event': '0',
    'robot': 'spark',
    'enemy': 'flora',
    'mobility': 'tracks',
    'enemyMobility': 'legs',
    'sound': false,
  });

void main() {
  test(
    'native position, wheels and tracks use actual distance at 30/60/120 Hz',
    () {
      final scenes = <GameSceneClock>[];
      for (final hz in [30, 60, 120]) {
        final clock = scene();
        clock.advance(0);
        for (var i = 0; i < hz * 1.5; i++) {
          clock.advance(1 / hz);
        }
        scenes.add(clock);
      }
      for (final clock in scenes.skip(1)) {
        expect(clock.player.center, closeTo(scenes.first.player.center, 1e-7));
        expect(
          clock.player.motor.distance,
          closeTo(scenes.first.player.motor.distance, 1e-6),
        );
        expect(
          clock.player.motor.wheelAngle,
          closeTo(scenes.first.player.motor.wheelAngle, 1e-6),
        );
        expect(
          clock.player.pose.head,
          closeTo(scenes.first.player.pose.head, 1e-7),
        );
      }
      for (final clock in scenes) {
        clock.dispose();
      }
    },
  );
  test('rapid feeding events never reset or cumulatively shrink the robot', () {
    final clock = scene();
    clock.update({...clock.data, 'action': 'feed', 'event': '1'});
    clock.advance(.25);
    for (var i = 2; i < 82; i++) {
      clock.update({...clock.data, 'action': 'joy', 'event': '$i'});
    }
    expect(clock.age, .25);
    expect(clock.action, 'feed');
    clock.advance(.25);
    expect(clock.age, .5);
    expect(clock.player.pose.extra['bodyscaleX'], 1);
    expect(clock.player.pose.extra['headscaleX'], 1);
    clock.dispose();
  });
  test(
    'inspection freezes patrol and pause freezes the local animation clock',
    () {
      final clock = scene()
        ..advance(0)
        ..advance(1);
      clock.camera(1.6);
      final x = clock.player.center;
      clock.advance(.6);
      expect(clock.player.center, closeTo(x, 1e-9));
      expect(clock.zoom, greaterThan(1.5));
      final age = clock.age;
      clock.suspended = true;
      clock.advance(100);
      expect(clock.age, age);
      clock.dispose();
    },
  );
  test('effects are bounded and eventually expire', () {
    final clock = scene();
    for (var i = 0; i < 200; i++) {
      clock.effects.burst(const Offset(100, 100), Colors.amber);
    }
    expect(clock.effects.particles.length, 96);
    clock.advance(5);
    expect(clock.effects.particles, isEmpty);
    clock.dispose();
  });
  test('touch movement uses the selected point, real distance and viewport bounds', () {
    final clock = scene()..viewport = const Size(844, 390)..advance(0);
    final before = clock.player.center;
    clock.moveTo(const Offset(790, 300));
    for (var i = 0; i < 120; i++) clock.advance(1 / 60);
    expect(clock.player.center, greaterThan(before + 40));
    expect(clock.player.center + 210 * clock.scale, lessThanOrEqualTo(844));
    expect(clock.player.motor.distance, greaterThan(0));
    expect(clock.player.facing, 1);
    clock.moveTo(const Offset(-200, 300));
    for (var i = 0; i < 120; i++) clock.advance(1 / 60);
    expect(clock.player.center - 210 * clock.scale, greaterThanOrEqualTo(0));
    expect(clock.player.facing, -1);
    clock.dispose();
  });
  test('touch following and hit testing respect camera zoom and pan', () {
    final clock = scene()..advance(0);
    clock.camera(1.6); clock.advance(1);
    clock.pan = const Offset(12, 6);
    final world = clock.target(clock.player);
    final screen = world * clock.zoom + Offset(clock.viewport.width * (1 - clock.zoom) / 2,
        clock.viewport.height * (1 - clock.zoom) / 2) + clock.pan;
    expect(clock.robotAt(screen), isTrue);
    expect(clock.robotAt(Offset.zero), isFalse);
    clock.pointAt(const Offset(380, 20));
    expect(clock.gaze.dx, greaterThan(0));
    expect(clock.gaze.dy, lessThan(0));
    clock.player.facing = -1;
    clock.pointAt(const Offset(380, 20));
    expect(clock.gaze.dx, lessThan(0), reason:'Mirrored eye coordinates must follow the same screen point');
    clock.dispose();
  });
  test('a jumping robot keeps the full touch region around its current body', () {
    final clock = scene()..advance(0);
    clock.player.pose.y = -60;
    final point = clock.target(clock.player) + Offset(0, 150 * clock.scale);
    expect(clock.robotAt(point), isTrue);
    clock.dispose();
  });
  test('rapid touches change reactions and demo timelines return to idle', () {
    final clock = scene()..advance(0);
    clock.react(); final first = clock.localAction;
    clock.advance(.1); clock.react();
    expect(clock.localAction, isNot(first));
    clock.advance(.1); clock.react();
    expect(clock.localAction, 'dance');
    clock.showcase('ultimate'); clock.advance(.8);
    expect(clock.signatureVisible, isTrue);
    clock.advance(2);
    expect(clock.signatureVisible, isFalse);
    clock.dispose();
  });
  test('battle speed keeps native projectiles synchronized with turn durations', () {
    for (final speed in [1.0, 1.5, 2.0]) {
      final clock = scene();
      clock.update({...clock.data, 'arena':true,'action':'attack','combatAction':'quick',
        'phase':'flight','animationSpeed':speed,'flightSeconds':.42,'event':'attack'});
      clock.advance(.21 / speed);
      expect(clock.progress, closeTo(.5, 1e-9));
      clock.dispose();
    }
  });
  test('hidden scenes and advertisement pauses stop all motion and particles', () {
    final clock = scene()..advance(1);
    final age = clock.age, x = clock.player.center;
    clock.hidden = true; clock.advance(60);
    expect(clock.age, age); expect(clock.player.center, x);
    clock.hidden = false; clock.update({...clock.data, 'paused':true}); clock.advance(60);
    expect(clock.age, age);
    clock.update({...clock.data, 'paused':false}); clock.advance(.1);
    expect(clock.age, greaterThan(age));
    clock.dispose();
  });
  test('all collection identities have distinct moving assemblies', () {
    final shapes = <String>{};
    for (final id in robotProfiles.keys) {
      final clock = scene();
      clock.update({
        ...clock.data,
        'robot': id,
        'event': id,
        'mobility': robotProfiles[id]!['mobility'],
      });
      clock.advance(2);
      shapes.add(
        '${clock.player.pose.extra}:${clock.player.pose.armL}:${clock.player.pose.head}',
      );
      clock.dispose();
    }
    expect(shapes.length, 32);
  });
  test(
    'all rigs keep their physical margins during movement and hit recoil',
    () {
      for (final size in [
        const Size(245, 270),
        const Size(320, 294),
        const Size(390, 294),
        const Size(844, 280),
        const Size(1280, 520),
      ]) {
        for (final arena in [false, true]) {
          for (final id in robotProfiles.keys) {
            final clock = scene()..viewport = size;
            clock.update({
              ...clock.data,
              'robot': id,
              'mobility': robotProfiles[id]!['mobility'],
              'arena': arena,
              'phase': arena ? 'impact' : 'workshop',
              'event': 'check',
              'damage': 20,
            });
            for (var frame = 0; frame < 240; frame++) {
              clock.advance(1 / 30);
              final half = (id == 'volt' ? 140 : 210) * clock.scale;
              expect(
                clock.player.center - half,
                greaterThanOrEqualTo(0),
                reason: '$id $size $arena',
              );
              expect(
                clock.player.center + half,
                lessThanOrEqualTo(size.width),
                reason: '$id $size $arena',
              );
              if (arena) {
                final enemyHalf = 210 * clock.scale;
                expect(clock.enemy.center - enemyHalf, greaterThanOrEqualTo(0));
                expect(
                  clock.enemy.center + enemyHalf,
                  lessThanOrEqualTo(size.width),
                );
              }
            }
            clock.dispose();
          }
        }
      }
    },
  );
}
