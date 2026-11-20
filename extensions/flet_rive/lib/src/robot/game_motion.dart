import 'dart:math' as math;
import 'dart:ui';

import 'motion_model.dart';

double unit(double x) => x.clamp(0.0, 1.0);
double smooth(double x) {
  x = unit(x);
  return x * x * (3 - 2 * x);
}

double pulse(double t, double start, double end) => t <= start || t >= end
    ? 0
    : math.sin(math.pi * (t - start) / (end - start));

/// Explicit, time-based poses. No per-frame incremented scale or rotation.
class GamePose {
  int mode = 0;
  final extra = <String, double>{
    for (var i = 0; i < 16; i++) 'joint$i': 0,
    for (var i = 0; i < 8; i++) 'segmentY$i': 95,
    'cryo': 0,
    'ion': 0,
    'blaster': 0,
    'magnetic': 0,
    'grenade': 0,
    'emp': 0,
    'drill': 0,
    'disc': 0,
    'repair': 0,
    'modArmor': 0,
    'modCore': 0,
    'modDrive': 0,
    'modDefense': 0,
    'modGadget': 0,
    'secondaryGun':0,'secondaryPods':0,'secondaryBlade':0,'secondaryOrb':0,
    'bodyscaleX': 1,
    'bodyscaleY': 1,
    'headscaleX': 1,
    'headscaleY': 1,
    'tracks': 1,
    'legs': 0,
    'hover': 0,
    'wheels': 0,
    'legL': 0,
    'legR': 0,
    'jet': 1,
    'leaf': 0,
    'fins': 0,
    'sun': 0,
    'gearAngle': 0,
    'laser': 0,
    'electric': 0,
    'machinegun': 0,
    'sword': 0,
    'flame': 0,
    'drone': 0,
    'gunRotor': 0,
    'barrel0X': -13,
    'barrel1X': 0,
    'barrel2X': 13,
  };
  double x = 0, y = 0, rotation = 0, head = 0, headY = -117;
  double body = 0, bodyY = 0, armL = .05, armR = -.05, foreL = 0, foreR = 0;
  double eyeX = 1, eyeY = 1, brow = 0, smile = 1, focus = 0, sad = 0, shock = 0;
  double deploy = 0, barrel = 18, fin = 0, shield = 0, aura = 0;
  String weapon = '';

  GamePose(double clock) {
    bodyY = -3 * (1 + math.sin(clock * 3));
    head = math.sin(clock * 1.7) * .055;
    headY -= 4 * math.sin(clock * 3 - .5);
    armL += .12 * math.sin(clock * 2.3);
    armR -= .12 * math.sin(clock * 2.3 + .8);
    eyeY = clock % 4.7 > 4.55 ? .12 : 1;
  }

  void blendFrom(GamePose old, double weight) {
    double mix(double a, double b) => a + (b - a) * weight;
    x = mix(old.x, x);
    y = mix(old.y, y);
    rotation = mix(old.rotation, rotation);
    head = mix(old.head, head);
    headY = mix(old.headY, headY);
    body = mix(old.body, body);
    bodyY = mix(old.bodyY, bodyY);
    armL = mix(old.armL, armL);
    armR = mix(old.armR, armR);
    foreL = mix(old.foreL, foreL);
    foreR = mix(old.foreR, foreR);
    eyeX = mix(old.eyeX, eyeX);
    eyeY = mix(old.eyeY, eyeY);
    brow = mix(old.brow, brow);
    smile = mix(old.smile, smile);
    focus = mix(old.focus, focus);
    sad = mix(old.sad, sad);
    shock = mix(old.shock, shock);
    deploy = mix(old.deploy, deploy);
    shield = mix(old.shield, shield);
    aura = mix(old.aura, aura);
    if (weapon.isEmpty && weight < 1) weapon = old.weapon;
  }

  void emotion(String name, double t) {
    final bounce = math.sin(t * 10);
    switch (name) {
      case 'joy':
      case 'feed':
      case 'victory':
        mode = 6;
        y -= 24 * bounce.abs();
        head = .17 * math.sin(t * 8);
        armL = 1.8 + .65 * bounce;
        armR = -1.8 - .65 * bounce;
        foreL = -.6;
        foreR = .6;
        body = .12 * math.sin(t * 6);
        eyeY = .58;
        eyeX = 1.3;
        smile = 1;
        if (name == 'feed') {
          armL = .6;
          foreL = -1.7;
          aura = .3;
        }
      case 'anger':
        smile = 0;
        focus = 1;
        brow = .48;
        eyeY = .6;
        head = -.11;
        body = .13;
        armL = .65;
        foreL = -1.3;
        armR = -.6;
        foreR = 1.3;
        y = -5 * bounce.abs();
      case 'fear':
        smile = 0;
        shock = .7;
        eyeX = .75;
        eyeY = 1.28;
        brow = -.4;
        head = .08 * math.sin(t * 28);
        body = -.2;
        armL = 1;
        armR = -1;
        foreL = -1.6;
        foreR = 1.6;
        x -= 17;
        y = 3;
      case 'surprise':
        smile = 0;
        shock = 1;
        eyeX = 1.3;
        eyeY = 1.35;
        brow = -.3;
        y = -32 * pulse(t, 0, .8);
        headY = -130;
        armL = 1.2;
        armR = -1.2;
        foreL = -.5;
        foreR = .5;
      case 'defeat':
        mode = 7;
        final fall = smooth(t / .65);
        smile = 0;
        sad = 1;
        eyeY = .35;
        brow = -.38;
        head = .42 * fall;
        headY = -117 + 23 * fall;
        body = -.22 * fall;
        bodyY = 18 * fall;
        rotation = -.2 * fall;
        y = 18 * fall;
        armL = -.25;
        armR = .3;
        foreL = .7;
        foreR = -.7;
      case 'dance':
        mode = 6;
        body = .22 * math.sin(t * 9);
        head = -.18 * math.sin(t * 9);
        armL = .8 + .9 * math.sin(t * 9);
        armR = -.8 + .9 * math.sin(t * 9);
        foreL = -1; foreR = 1;
        y -= 15 * math.sin(t * 9).abs();
        smile = 1; eyeY = .65;
      case 'inspect':
        head = .35 * math.sin(t * 3.8);
        armR = -.5; foreR = -1;
        armL = .25; foreL = -.6;
        eyeY = .8; brow = -.18;
        body = -.08 * math.sin(t * 3.8);
    }
  }

  void prepare(String type, double t) {
    mode = 4;
    weapon = type;
    deploy = smooth(t / .4);
    fin = deploy * .5;
    emotion('anger', t);
    x -= 24 * deploy;
    y += 10 * deploy;
    head = -.13 * deploy;
    armR = -1.48 * deploy;
    foreR = -.12 * deploy;
    armL = .5;
    foreL = -1.6;
    body = -.16 * deploy;
    aura = {'electric', 'plasma', 'ion', 'cryo', 'emp', 'magnetic'}.contains(type) ? .15 * deploy : 0;
    if (type == 'sniper') {
      armL = -1.05 * deploy;
      foreL = -1.45 * deploy;
      eyeY = .35;
    }
    if (type == 'fist') {
      armR = -.5;
      foreR = -1.5;
      body = -.25;
    }
    if (type == 'shield' || type == 'repair') {
      shield = type == 'shield' ? deploy : 0;
      aura = .5;
    }
  }

  void fire(String type, double t) {
    prepare(type, 1);
    mode = 2;
    final recoil = math.exp(-t * 10) * math.sin(t * 27);
    x = -35 * recoil;
    rotation = -.13 * recoil;
    body = -.2 * recoil;
    head = .15 * recoil;
    armR = -1.53 + .3 * recoil;
    foreR = -.07 + .26 * recoil;
    barrel = 18 - 17 * math.exp(-t * 14);
    if (type == 'sniper') {
      x -= 38 * math.exp(-t * 8);
      head -= .18 * math.exp(-t * 9);
    }
    if (type == 'fist') {
      armR = -1.72;
      foreR = .22;
      body = .23;
      rotation = .11;
    }
    if (type == 'shield') shield = .95;
  }

  void hit(double t, double strength) {
    mode = 5;
    final impact = math.exp(-t * 6);
    x -= (28 + 35 * strength) * impact;
    y -= 17 * pulse(t, 0, .45);
    rotation = -.2 * impact;
    head = -.38 * impact;
    headY += 14 * impact;
    body = -.24 * impact;
    armL = -1.1 * impact;
    armR = .75 * impact;
    smile = 0;
    shock = impact;
    eyeY = .35 + .65 * (1 - impact);
  }

  Map<String, double> get values => {
    ...extra,
    'Robot.x': 210 + x,
    'Robot.y': 276 + y,
    'Robot.rotation': rotation,
    'Head.y': headY,
    'Head.rotation': head,
    'Body.y': bodyY,
    'Body.rotation': body,
    'Arm L.rotation': armL,
    'Arm R.rotation': armR,
    'Forearm L.rotation': foreL,
    'Forearm R.rotation': foreR,
    'Eyes.scaleX': eyeX,
    'Eyes.scaleY': eyeY,
    'Smile.opacity': smile,
    'Focus mouth.opacity': focus,
    'Sad mouth.opacity': sad,
    'Brow L.rotation': brow,
    'Brow R.rotation': -brow,
    'Shield.opacity': shield,
    'Charge aura.opacity': aura,
    'shock': shock,
    for (final type in [
      'laser',
      'electric',
      'machinegun',
      'sword',
      'flame',
      'drone',
      'cryo',
      'ion',
      'blaster',
      'magnetic',
      'grenade',
      'emp',
      'drill',
      'disc',
      'repair',
    ])
      type: weapon == type ? 1 : 0,
    'plasma': weapon == 'plasma' ? 1 : 0,
    'sniper': weapon == 'sniper' ? 1 : 0,
    'fist': weapon == 'fist' ? 1 : 0,
    'rocket': weapon == 'rocket' ? 1 : 0,
    'deploy': math.max(.01, deploy),
    'palm': {'shield', 'repair', 'charge', 'dodge', ''}.contains(weapon)
        ? 1
        : 1 - deploy,
    'barrelY': barrel,
    'fin': fin,
    'finBack': -fin,
    'missile0': 34 - 18 * deploy,
    'missile1': 34 - 18 * deploy,
  };
}

class GameActor {
  final motor = RobotMotor();
  GamePose pose = GamePose(0);
  double center = 0, previousCenter = 0, facing = 1;
  String mobility = 'tracks';
  void travel(double center, double scale, double dt) {
    if (dt > 0 && scale > 0) {
      final delta = (center - previousCenter) / scale;
      motor.distance += delta * facing;
      motor.velocity = delta / dt;
    }
    previousCenter = center;
    this.center = center;
  }
}

class GameParticle {
  GameParticle(
    this.origin,
    this.velocity,
    this.life,
    this.radius,
    this.color,
    this.smoke,
  );
  final Offset origin, velocity;
  final double life, radius;
  final Color color;
  final bool smoke;
  double age = 0;
  Offset get position =>
      origin + velocity * age + Offset(0, (smoke ? -30 : 110) * age * age);
}

/// Bounded pool; analytic particle motion stays independent of refresh rate.
class GameEffects {
  int limit = 96;
  final particles = <GameParticle>[];
  final random = math.Random(83);
  void burst(
    Offset position,
    Color color, {
    bool smoke = false,
    int count = 28,
  }) {
    for (var i = 0; i < count && particles.length < limit; i++) {
      final angle = random.nextDouble() * math.pi * 2;
      final speed = smoke
          ? 12 + random.nextDouble() * 55
          : 60 + random.nextDouble() * 230;
      particles.add(
        GameParticle(
          position,
          Offset(math.cos(angle), math.sin(angle)) * speed,
          smoke
              ? .65 + random.nextDouble() * .5
              : .2 + random.nextDouble() * .65,
          smoke
              ? 7 + random.nextDouble() * 11
              : 1.5 + random.nextDouble() * 2.8,
          color,
          smoke,
        ),
      );
    }
  }

  void advance(double dt) {
    for (final p in particles) {
      p.age += dt;
    }
    particles.removeWhere((p) => p.age >= p.life);
    if (particles.length > limit) particles.removeRange(0, particles.length - limit);
  }
}
