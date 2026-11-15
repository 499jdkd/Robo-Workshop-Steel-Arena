import 'dart:math' as math;

/// Presentation only. No combat results, inventory or player save live here.
enum RobotAction { idle, move, attack, defend, charge, hit, victory, defeat }

const actionSeconds = <RobotAction, double>{
  RobotAction.attack: 1.1,
  RobotAction.hit: .8,
  RobotAction.defeat: 1.5,
};

const wheelRadius = 23.5;
const trackRadius = 29.0;
const trackStraight = 134.0;
const trackLength = trackStraight * 2 + math.pi * 2 * trackRadius;

({double x, double y, double rotation}) treadAt(double distance) {
  var s = distance % trackLength;
  if (s < trackStraight) return (x: -67 + s, y: -29, rotation: 0);
  s -= trackStraight;
  if (s < math.pi * trackRadius) {
    final a = s / trackRadius - math.pi / 2;
    return (
      x: 67 + trackRadius * math.cos(a),
      y: trackRadius * math.sin(a),
      rotation: a + math.pi / 2,
    );
  }
  s -= math.pi * trackRadius;
  if (s < trackStraight) return (x: 67 - s, y: 29, rotation: math.pi);
  final a = (s - trackStraight) / trackRadius + math.pi / 2;
  return (
    x: -67 + trackRadius * math.cos(a),
    y: trackRadius * math.sin(a),
    rotation: a + math.pi / 2,
  );
}

/// Exact exponential velocity integration; independent of the display rate.
class RobotMotor {
  double x = 0;
  double velocity = 0;
  double distance = 0;
  double facing = 1;

  void step(double seconds, double target) {
    if (!seconds.isFinite || seconds <= 0 || !target.isFinite) return;
    const damping = 7.0;
    final decay = math.exp(-damping * seconds);
    final delta =
        target * seconds + (velocity - target) * (1 - decay) / damping;
    x += delta;
    distance += delta * facing;
    velocity = target + (velocity - target) * decay;
  }

  double get wheelAngle => (distance / wheelRadius) % (math.pi * 2);
  double get trackDistance => distance % trackLength;
}

class RobotPresentation {
  final motor = RobotMotor();
  RobotAction action = RobotAction.idle;
  double age = 0;
  double clock = 0;
  double patrolTime = 0;
  double direction = 1;
  int lastCommand = -1;
  bool autonomous = true;
  bool reducedMotion = false;
  bool arena = false;
  bool inspecting = false;

  bool request(RobotAction next, int command) {
    if (command <= lastCommand) return false;
    lastCommand = command;
    action = next;
    age = 0;
    return true;
  }

  void advance(double seconds, {double span = 115}) {
    if (!seconds.isFinite || seconds <= 0) return;
    clock += seconds;
    age += seconds;
    var motionSeconds = seconds;
    final duration = actionSeconds[action];
    if (duration != null &&
        age + 1e-9 >= duration &&
        action != RobotAction.defeat) {
      motionSeconds = math.max(0, age - duration);
      action = RobotAction.idle;
      age = motionSeconds;
    }
    final moving =
        !reducedMotion &&
        !inspecting &&
        !arena &&
        (action == RobotAction.move ||
            (autonomous && action == RobotAction.idle));
    // Smooth periodic patrol, evaluated in continuous time. Its distance is
    // integrated from the actual displacement, not a frame-based spin counter.
    if (moving && autonomous) {
      final previous = patrolTime * .48;
      patrolTime += motionSeconds;
      final phase = patrolTime * .48;
      final position = span * math.sin(phase);
      final velocity = span * .48 * math.cos(phase);
      final facing = velocity < 0 ? -1.0 : 1.0;
      motor.distance += span * (_arc(phase) - _arc(previous));
      motor.x = position;
      motor.velocity = velocity;
      motor.facing = facing;
    } else if (moving) {
      _advanceBounded(motionSeconds, span);
    } else {
      motor.velocity = 0;
    }
  }

  void _advanceBounded(double seconds, double span) {
    if (span <= 0) {
      motor.velocity = 0;
      return;
    }
    var remaining = seconds;
    motor.x = motor.x.clamp(-span, span);
    motor.velocity = motor.velocity.abs() * direction;
    while (remaining > 1e-10) {
      final target = 75 * direction;
      double positionAt(double dt) =>
          motor.x +
          target * dt +
          (motor.velocity - target) * (1 - math.exp(-7 * dt)) / 7;
      if (positionAt(remaining).abs() <= span) {
        motor.facing = direction;
        motor.step(remaining, target);
        break;
      }
      var low = 0.0, high = remaining;
      for (var i = 0; i < 42; i++) {
        final middle = (low + high) / 2;
        if (positionAt(middle).abs() > span) {
          high = middle;
        } else {
          low = middle;
        }
      }
      motor.facing = direction;
      motor.step(high, target);
      motor.x = span * direction;
      remaining -= high;
      direction = -direction;
      motor.velocity = -motor.velocity;
    }
  }

  static double _arc(double phase) {
    final periods = (phase / math.pi).floor();
    final rest = phase - periods * math.pi;
    return periods * 2 +
        (rest <= math.pi / 2 ? math.sin(rest) : 2 - math.sin(rest));
  }

  RobotAction get visualAction =>
      !arena &&
          !inspecting &&
          autonomous &&
          action == RobotAction.idle &&
          !reducedMotion
      ? RobotAction.move
      : action;
}

class SparkParticle {
  SparkParticle(
    this.originX,
    this.originY,
    this.vx,
    this.vy,
    this.lifetime,
    this.hue,
  );
  final double originX, originY, vx, vy, lifetime, hue;
  double age = 0;
  double get x => originX + vx * age;
  double get y => originY + vy * age + 95 * age * age;
  double get opacity => (1 - age / lifetime).clamp(0, 1);
}

/// A bounded pool, sampled from elapsed time and not tied to frame count.
class SparkEffects {
  static const maxParticles = 40;
  final particles = <SparkParticle>[];
  double impactAge = 99;
  double flash = 0;
  final _random = math.Random(73);

  void burst(double x, double y, {int count = 14, bool reducedMotion = false}) {
    impactAge = 0;
    if (reducedMotion) return;
    for (var i = 0; i < count && particles.length < maxParticles; i++) {
      final a = _random.nextDouble() * math.pi * 2;
      final speed = 35 + _random.nextDouble() * 100;
      particles.add(
        SparkParticle(
          x,
          y,
          math.cos(a) * speed,
          math.sin(a) * speed - 40,
          .3 + _random.nextDouble() * .4,
          _random.nextDouble(),
        ),
      );
    }
  }

  void advance(double seconds) {
    impactAge += seconds;
    flash = math.max(0, 1 - impactAge / .16);
    for (final particle in particles) {
      particle.age += seconds;
    }
    particles.removeWhere((p) => p.age >= p.lifetime);
  }

  double get shake => impactAge < .25
      ? math.sin(impactAge * 97) * 4 * (1 - impactAge / .25)
      : 0;
}
