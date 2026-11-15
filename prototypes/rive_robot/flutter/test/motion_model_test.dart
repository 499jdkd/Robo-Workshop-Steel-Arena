import 'dart:math' as math;
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/motion_model.dart';

void main() {
  test('exact integration matches 30/60/120 Hz and irregular frames', () {
    final samples = <RobotMotor>[];
    for (final fps in [30, 60, 120]) {
      final m = RobotMotor();
      for (var i = 0; i < fps * 8; i++) {
        m.step(1 / fps, 75);
      }
      samples.add(m);
    }
    for (final m in samples) {
      expect(m.x, closeTo(samples.first.x, 1e-9));
      expect(m.distance, closeTo(m.x, 1e-9));
      expect(
        m.wheelAngle,
        closeTo((m.distance / wheelRadius) % (math.pi * 2), 1e-9),
      );
    }
    final uneven = RobotMotor();
    for (var i = 0; i < 100; i++) {
      uneven.step(.013, 75);
      uneven.step(.067, 75);
    }
    expect(uneven.x, closeTo(samples.first.x, 1e-9));
  });
  test(
    'autonomous patrol distance is stable across turns and refresh rates',
    () {
      final results = <RobotPresentation>[];
      for (final fps in [30, 60, 120]) {
        final robot = RobotPresentation();
        for (var i = 0; i < fps * 40; i++) {
          robot.advance(1 / fps);
        }
        results.add(robot);
      }
      for (final robot in results) {
        expect(robot.motor.x, closeTo(results.first.motor.x, 1e-7));
        expect(
          robot.motor.distance,
          closeTo(results.first.motor.distance, 1e-7),
        );
        expect(robot.motor.x.abs(), lessThanOrEqualTo(115));
      }
    },
  );
  test('idle wheels stop and backwards wheels reverse without angle jumps', () {
    final m = RobotMotor();
    m.step(.5, 60);
    final angle = m.wheelAngle;
    m.velocity = 0;
    m.step(1, 0);
    expect(m.wheelAngle, angle);
    m.step(1, -60);
    expect(m.velocity, lessThan(0));
    expect(m.distance, lessThan(0));
  });
  test('manual movement reflects at the same time at every refresh rate', () {
    final values = <RobotPresentation>[];
    for (final fps in [30, 60, 120]) {
      final r = RobotPresentation()..autonomous = false;
      r.request(RobotAction.move, 1);
      for (var i = 0; i < fps * 20; i++) {
        r.advance(1 / fps);
      }
      values.add(r);
    }
    for (final r in values) {
      expect(r.motor.x, closeTo(values.first.motor.x, 1e-6));
      expect(r.motor.distance, closeTo(values.first.motor.distance, 1e-6));
    }
  });
  test(
    'one-shot recovery retains fractional time and inspection stops travel',
    () {
      final values = <RobotPresentation>[];
      for (final fps in [30, 60, 120]) {
        final r = RobotPresentation();
        r.request(RobotAction.attack, 1);
        for (var i = 0; i < fps * 6; i++) {
          r.advance(1 / fps);
        }
        values.add(r);
      }
      for (final r in values) {
        expect(r.motor.x, closeTo(values.first.motor.x, 1e-6));
        final x = r.motor.x, d = r.motor.distance;
        r.inspecting = true;
        r.advance(.37);
        expect(r.motor.x, x);
        expect(r.motor.distance, d);
      }
    },
  );
  test('treads follow a continuous closed capsule at constant arc length', () {
    for (final s in [
      0.0,
      134.0,
      134 + math.pi * 29,
      268 + math.pi * 29,
      trackLength,
    ]) {
      final a = treadAt(s - 1e-5), b = treadAt(s + 1e-5);
      expect(
        math.sqrt(math.pow(a.x - b.x, 2) + math.pow(a.y - b.y, 2)),
        lessThan(.00003),
      );
    }
    final start = treadAt(3), end = treadAt(3 + trackLength * 100);
    expect(start.x, closeTo(end.x, 1e-9));
    expect(start.y, closeTo(end.y, 1e-9));
  });
  test('actions deduplicate, recover and preserve defeat', () {
    final r = RobotPresentation()..autonomous = false;
    expect(r.request(RobotAction.attack, 1), isTrue);
    r.advance(.5);
    expect(r.request(RobotAction.attack, 1), isFalse);
    expect(r.age, .5);
    r.advance(.6);
    expect(r.action, RobotAction.idle);
    r.request(RobotAction.defeat, 2);
    r.advance(9);
    expect(r.action, RobotAction.defeat);
  });
  test(
    'effect pool is bounded and particles expire without frame dependence',
    () {
      final e = SparkEffects();
      for (var i = 0; i < 100; i++) {
        e.burst(1, 2);
      }
      expect(e.particles.length, SparkEffects.maxParticles);
      e.advance(1);
      expect(e.particles, isEmpty);
      expect(e.shake, 0);
      e.burst(1, 2, reducedMotion: true);
      expect(e.particles, isEmpty);
    },
  );
}
