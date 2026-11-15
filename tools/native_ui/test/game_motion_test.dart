import 'package:flet_rive/flet_rive.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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
  test('all eight identities have distinct moving assemblies', () {
    final shapes = <String>{};
    for (final id in [
      'spark',
      'volt',
      'flora',
      'forge',
      'nova',
      'glacier',
      'aegis',
      'solar',
    ]) {
      final clock = scene();
      clock.update({
        ...clock.data,
        'robot': id,
        'event': id,
        'mobility':
            {
              'volt': 'hover',
              'flora': 'legs',
              'nova': 'hover',
              'glacier': 'hover',
              'solar': 'hover',
            }[id] ??
            'tracks',
      });
      clock.advance(2);
      shapes.add(
        '${clock.player.pose.extra}:${clock.player.pose.armL}:${clock.player.pose.head}',
      );
      clock.dispose();
    }
    expect(shapes.length, 8);
  });
}
