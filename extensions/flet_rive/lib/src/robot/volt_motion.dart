import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'game_motion.dart';

/// Volt is animated from semantic actions on the local Flutter clock. All
/// values are sampled from absolute time, so a dropped frame cannot accumulate
/// joint drift, change the length of a dash, or replay an impact sound.
const voltActionSeconds = <String, double>{
  'attack': .94,
  'quick': .68,
  'special': 1.55,
  'guard': 1.2,
  'dodge': .82,
  'charge': 1.45,
  'ultimate': 2.55,
  'victory': 2.2,
  'defeat': 2.6,
  'joy': 1.1,
  'jump': 1.25,
  'surprise': 1.1,
  'anger': 1.25,
  'dance': 2.2,
  'inspect': 1.7,
};

class VoltCue {
  const VoltCue(this.at, this.name);
  final double at;
  final String name;
}

/// Original coil sounds, placed at mechanical charge/release milestones.
const voltCues = <String, List<VoltCue>>{
  'attack': [VoltCue(.22, 'volt_pulse')],
  'quick': [VoltCue(.12, 'deploy'), VoltCue(.26, 'volt_pulse')],
  'special': [VoltCue(.05, 'volt_charge'), VoltCue(.46, 'volt_pulse')],
  'guard': [VoltCue(.14, 'shield')],
  'dodge': [VoltCue(.16, 'volt_pulse')],
  'charge': [VoltCue(.15, 'volt_charge'), VoltCue(.52, 'repair')],
  'ultimate': [
    VoltCue(.04, 'volt_charge'),
    VoltCue(.31, 'ion'),
    VoltCue(.62, 'volt_storm'),
    VoltCue(.72, 'impact'),
  ],
  'victory': [VoltCue(.08, 'victory'), VoltCue(.48, 'volt_pulse')],
  'defeat': [VoltCue(.12, 'volt_shutdown')],
  'jump': [VoltCue(.18, 'deploy')],
  'surprise': [VoltCue(.16, 'volt_pulse')],
};

Iterable<String> voltCuesCrossed(
  String action,
  double before,
  double after,
) sync* {
  if (!before.isFinite || !after.isFinite || after < before) return;
  for (final cue in voltCues[action] ?? const <VoltCue>[]) {
    if (before < cue.at && after >= cue.at) yield cue.name;
  }
}

class VoltFrame {
  const VoltFrame({
    required this.action,
    required this.t,
    this.coilGlow = .35,
    this.coreGlow = .4,
    this.charge = 0,
    this.discharge = 0,
    this.shield = 0,
    this.trail = 0,
    this.shockwave = 0,
    this.flash = 0,
    this.smoke = 0,
    this.sparks = 0,
    this.power = 1,
  });
  final String action;
  final double t,
      coilGlow,
      coreGlow,
      charge,
      discharge,
      shield,
      trail,
      shockwave,
      flash,
      smoke,
      sparks,
      power;
}

double _ramp(double t, double begin, double end) =>
    smooth((t - begin) / (end - begin));
double _hold(double t, double begin, double peak, double release, double end) =>
    _ramp(t, begin, peak) * (1 - _ramp(t, release, end));
double _ring(double t, double begin, double end) =>
    unit((t - begin) / (end - begin));

/// joint0/1: left/right mast; joint2/3: contact petals; joint4: core rotor;
/// joint5/6: chest shutters. The common Rive view-model already exposes them.
/// Call after the common locomotion style, before the Rive VM is advanced.
VoltFrame applyVoltPose(
  GamePose p,
  String action,
  double normalizedT, {
  String equippedWeapon = '',
  double clock = 0,
}) {
  final t = normalizedT.isFinite ? unit(normalizedT) : 0.0;
  final idle = .5 + .5 * math.sin(clock * 3.2);
  var light = .32 + .07 * idle, core = .38 + .08 * idle;
  var charge = 0.0, discharge = 0.0, shield = 0.0, trail = 0.0;
  var wave = 0.0, flash = 0.0, smoke = 0.0, sparks = 0.0, power = 1.0;
  final f = p.extra;
  p.weapon = equippedWeapon;
  p.deploy = equippedWeapon.isEmpty ? 0 : .55;
  // Idle suspension, the head gimbal and the core spin have separate phases.
  f['joint0'] = .035 * math.sin(clock * 2.1);
  f['joint1'] = -.035 * math.sin(clock * 2.1 + .45);
  f['joint2'] = .04 * math.sin(clock * 2.8);
  f['joint3'] = -.04 * math.sin(clock * 2.8);
  f['joint4'] = clock * .35;
  f['joint5'] = .025 * math.sin(clock * 1.8);
  f['joint6'] = -.025 * math.sin(clock * 1.8);
  final settle = 1 - _ramp(t, .78, 1);
  switch (action) {
    case 'attack':
      final load = _hold(t, 0, .18, .22, .46);
      final kick = _hold(t, .22, .27, .34, .7);
      p.mode = t < .22 ? 4 : 2;
      p.x -= 7 * load + 17 * kick;
      p.body = -.1 * load - .17 * kick;
      p.head = .09 * kick;
      p.armR = -.3 - .7 * load + .24 * kick;
      p.foreR = -.25 * load;
      p.armL = .25 + .22 * load;
      f['joint0'] = .18 * load;
      f['joint1'] = -.5 * load + .24 * kick;
      f['joint2'] = .55 * load;
      f['joint3'] = -.85 * load;
      f['joint5'] = -.12 * load;
      f['joint6'] = .12 * load;
      charge = load;
      discharge = _hold(t, .22, .26, .4, .58);
      light += .6 * load + .55 * discharge;
      core += .4 * load;
      p.focus = load;
      p.smile = 1 - load;
    case 'quick':
      final crouch = _hold(t, 0, .1, .14, .25);
      final dash = _hold(t, .12, .28, .4, .83);
      final recoil = _hold(t, .27, .32, .39, .65);
      p.mode = 2;
      p.x += -12 * crouch + 61 * dash - 9 * recoil;
      p.y += 8 * crouch - 11 * dash;
      p.body = -.22 * crouch + .2 * dash;
      p.head = -.14 * dash;
      p.armL = .5 + .4 * dash;
      p.armR = -.4 - .55 * dash;
      p.foreL = -.65 * dash;
      p.foreR = .55 * dash;
      f['joint0'] = -.28 * dash;
      f['joint1'] = -.55 * dash;
      f['joint2'] = .7 * dash;
      f['joint3'] = -.7 * dash;
      f['jet'] = 1 + .7 * dash;
      discharge = _hold(t, .26, .3, .4, .54);
      trail = dash;
      light += .7 * discharge;
      core += .45 * dash;
      p.eyeY = 1 - .25 * dash;
      p.focus = dash;
      p.smile = 1 - dash;
    case 'special':
      final load = _hold(t, 0, .38, .46, .8);
      final kick = _hold(t, .46, .51, .58, .84);
      p.mode = t < .46 ? 4 : 2;
      p.y -= 11 * load;
      p.x -= 24 * kick;
      p.body = -.16 * load - .15 * kick;
      p.head = .1 * kick - .07 * load;
      p.armL = .15 + .95 * load;
      p.armR = -.15 - .95 * load;
      p.foreL = -.55 * load;
      p.foreR = .55 * load;
      f['joint0'] = .44 * load;
      f['joint1'] = -.44 * load;
      f['joint2'] = .92 * load;
      f['joint3'] = -.92 * load;
      f['joint4'] = clock * .35 + 2.5 * load;
      f['joint5'] = -.3 * load;
      f['joint6'] = .3 * load;
      charge = load;
      discharge = _hold(t, .46, .5, .65, .8);
      light += .8 * load;
      core += .65 * load;
      p.focus = load;
      p.smile = 1 - load;
      p.eyeY = 1 - .3 * load;
    case 'guard':
      final hold = _hold(t, 0, .2, .72, 1);
      p.mode = 3;
      p.y += 6 * hold;
      p.armL = .3 + .65 * hold;
      p.armR = -.3 - .65 * hold;
      p.foreL = -.7 * hold;
      p.foreR = .7 * hold;
      p.head = -.08 * hold;
      p.body = -.08 * hold;
      f['joint0'] = -.3 * hold;
      f['joint1'] = .3 * hold;
      f['joint2'] = .85 * hold;
      f['joint3'] = -.85 * hold;
      p.shield = 0; // The electrical shell has its own bounded painter.
      shield = hold;
      light += .55 * hold;
      core += .35 * hold;
      p.focus = hold;
      p.smile = 1 - hold;
    case 'dodge':
      final load = _hold(t, 0, .12, .14, .3);
      final dash = _hold(t, .14, .3, .48, .94);
      p.mode = 1;
      p.x += 8 * load - 62 * dash;
      p.y -= 15 * dash;
      p.rotation = -.15 * dash;
      p.body = .18 * load - .17 * dash;
      p.head = .17 * dash;
      p.armL = -.2 - .55 * dash;
      p.armR = .2 + .55 * dash;
      f['joint0'] = -.35 * dash;
      f['joint1'] = .35 * dash;
      f['joint2'] = .45 * dash;
      f['joint3'] = -.45 * dash;
      f['jet'] = 1 + .75 * dash;
      light += .5 * dash;
      trail = dash;
      p.eyeY = 1 - .2 * dash;
      p.focus = dash;
      p.smile = 1 - dash;
    case 'charge':
      final connect = _hold(t, 0, .34, .7, 1);
      p.mode = 4;
      p.y -= 8 * connect;
      p.armL = .15 + .8 * connect;
      p.armR = -.15 - .8 * connect;
      p.foreL = -.8 * connect;
      p.foreR = .8 * connect;
      p.head = -.12 * connect;
      f['joint0'] = .72 * connect;
      f['joint1'] = -.72 * connect;
      f['joint2'] = .8 * connect;
      f['joint3'] = -.8 * connect;
      f['joint4'] = clock * .35 + t * 5 * connect;
      f['joint5'] = -.42 * connect;
      f['joint6'] = .42 * connect;
      charge = connect;
      light += .6 * connect;
      core += .7 * connect;
      p.eyeY = 1 - .4 * connect;
      p.smile = 1;
    case 'ultimate':
      final crouch = _hold(t, 0, .1, .13, .3);
      final flight = _hold(t, .1, .34, .74, 1);
      final open = _hold(t, .17, .44, .76, .99);
      final kick = _hold(t, .62, .66, .71, .88);
      p.mode = t < .62 ? 4 : 2;
      p.y += 10 * crouch - 82 * flight;
      p.x -= 19 * kick;
      p.body = -.13 * open - .2 * kick;
      p.head = -.1 * open + .14 * kick;
      p.armL = .1 + 1.75 * open;
      p.armR = -.1 - 1.75 * open;
      p.foreL = -.72 * open;
      p.foreR = .72 * open;
      f['joint0'] = -.78 * open;
      f['joint1'] = .78 * open;
      f['joint2'] = 1.12 * open;
      f['joint3'] = -1.12 * open;
      f['joint4'] = clock * .35 + 7 * t * open;
      f['joint5'] = -.7 * open;
      f['joint6'] = .7 * open;
      f['jet'] = 1 + .8 * flight;
      charge = _hold(t, .12, .57, .62, .78);
      discharge = _hold(t, .62, .65, .76, .9);
      light += .9 * open;
      core += .9 * charge;
      wave = t > .67 && t < 1 ? _ring(t, .67, 1) : 0;
      flash = pulse(t, .62, .72);
      sparks = open;
      p.focus = open;
      p.smile = 1 - open;
      p.brow = .22 * open;
      p.eyeY = 1 - .28 * open;
    case 'joy':
    case 'feed':
      final delight = math.sin(math.pi * t);
      p.mode = 6;
      p.y -= 18 * math.sin(t * math.pi * 2).abs() * settle;
      p.body = .12 * math.sin(t * math.pi * 3) * settle;
      p.head = -.15 * math.sin(t * math.pi * 3) * settle;
      p.armL = .1 + 1.25 * delight;
      p.armR = -.1 - 1.1 * delight;
      p.foreL = -.5 * delight;
      p.foreR = .65 * delight;
      p.eyeY = 1 - .42 * delight;
      p.eyeX = 1 + .15 * delight;
      p.smile = 1;
      light += .3 * delight;
      sparks = .4 * delight;
      f['joint0'] = -.22 * delight;
      f['joint1'] = .22 * delight;
    case 'jump':
      final crouch = _hold(t, 0, .14, .18, .3);
      final airborne = pulse(t, .18, .78);
      final land = pulse(t, .78, 1);
      p.mode = 6;
      p.y += 11 * crouch - 57 * airborne + 7 * land;
      p.body = -.14 * crouch + .13 * land;
      p.head = .12 * crouch - .13 * airborne;
      p.armL = .1 + 1.3 * airborne;
      p.armR = -.1 - 1.3 * airborne;
      p.foreL = -.55 * airborne;
      p.foreR = .55 * airborne;
      f['joint0'] = -.3 * airborne;
      f['joint1'] = .3 * airborne;
      f['jet'] = 1 + .8 * airborne;
      p.eyeY = 1 - .35 * airborne;
      light += .35 * airborne;
      sparks = .45 * land;
    case 'surprise':
      final startle = _hold(t, 0, .13, .35, 1);
      p.mode = 5;
      p.y -= 17 * startle;
      p.x -= 9 * startle;
      p.headY -= 8 * startle;
      p.head = -.13 * startle;
      p.armL = .15 + 1.15 * startle;
      p.armR = -.15 - 1.15 * startle;
      p.foreL = -.6 * startle;
      p.foreR = .6 * startle;
      p.smile = 1 - startle;
      p.shock = startle;
      p.eyeY = 1 + .3 * startle;
      p.eyeX = 1 + .24 * startle;
      p.brow = -.3 * startle;
      f['joint0'] = -.4 * startle;
      f['joint1'] = .4 * startle;
      sparks = .5 * pulse(t, .1, .5);
      light += .45 * startle;
    case 'anger':
      final grump = _hold(t, 0, .2, .63, 1);
      p.smile = 1 - grump;
      p.focus = grump;
      p.brow = .5 * grump;
      p.eyeY = 1 - .4 * grump;
      p.head = -.16 * grump;
      p.armL = .1 + .75 * grump;
      p.armR = -.1 - .75 * grump;
      p.foreL = -1.15 * grump;
      p.foreR = 1.15 * grump;
      p.body = .09 * math.sin(t * 25) * grump;
      f['joint0'] = -.18 * grump;
      f['joint1'] = .18 * grump;
      light += .35 * grump;
      sparks = .3 * grump;
    case 'dance':
      final dance = _hold(t, 0, .14, .84, 1);
      final beat = t * math.pi * 6;
      p.mode = 6;
      p.body = .18 * math.sin(beat) * dance;
      p.head = -.2 * math.sin(beat - .4) * dance;
      p.y -= 13 * math.sin(beat).abs() * dance;
      p.armL = .1 + (1 + .65 * math.sin(beat)) * dance;
      p.armR = -.1 - (1 - .65 * math.sin(beat)) * dance;
      p.foreL = -.7 * dance;
      p.foreR = .7 * dance;
      f['joint0'] = -.2 * dance + .2 * math.sin(beat - .6) * dance;
      f['joint1'] = .2 * dance + .2 * math.sin(beat - .6) * dance;
      f['joint4'] = clock * .35 + beat * dance;
      light += .4 * dance;
      sparks = .5 * dance;
      p.eyeY = 1 - .35 * dance;
      p.smile = 1;
    case 'inspect':
      final look = _hold(t, 0, .2, .7, 1);
      p.head = .32 * math.sin(t * math.pi * 2) * look;
      p.body = -.06 * math.sin(t * math.pi * 2 - .5) * look;
      p.armR = -.1 - .55 * look;
      p.foreR = -1.1 * look;
      f['joint1'] = -.32 * look;
      f['joint3'] = -.45 * look;
      p.eyeY = 1 - .15 * look;
      p.brow = -.12 * look;
      light += .3 * look;
    case 'victory':
      final cheer = _hold(t, 0, .16, .82, 1);
      final bounce = math.sin(t * math.pi * 4).abs() * cheer;
      p.mode = 6;
      p.y -= 31 * bounce;
      p.head = .16 * math.sin(t * math.pi * 4) * cheer;
      p.body = -.13 * math.sin(t * math.pi * 4) * cheer;
      p.armL = .1 + 2.1 * cheer;
      p.armR = -.1 - 2.1 * cheer;
      p.foreL = -.7 * cheer;
      p.foreR = .7 * cheer;
      f['joint0'] = -.55 * cheer;
      f['joint1'] = .55 * cheer;
      f['joint2'] = .8 * cheer;
      f['joint3'] = -.8 * cheer;
      p.eyeY = 1 - .45 * cheer;
      p.smile = 1;
      light += .65 * cheer;
      core += .45 * cheer;
      sparks = cheer;
    case 'defeat':
      final fail = _ramp(t, .06, .95);
      final stutter = (1 - fail) * .5 * (1 + math.sin(t * 72));
      p.mode = 7;
      power = 1 - fail;
      p.y += 27 * fail;
      p.bodyY += 13 * fail;
      p.body = -.2 * fail;
      p.head = .3 * fail;
      p.headY += 12 * fail;
      p.armL = .05 - .35 * fail;
      p.armR = -.05 + .35 * fail;
      p.foreL = .6 * fail;
      p.foreR = -.6 * fail;
      f['joint0'] = -.1 - .32 * fail;
      f['joint1'] = .1 + .32 * fail;
      f['joint2'] = .35 * (1 - fail);
      f['joint3'] = -.35 * (1 - fail);
      f['joint4'] = math.sin(t * 9) * .35 * (1 - fail);
      f['joint5'] = -.1 * (1 - fail);
      f['joint6'] = .1 * (1 - fail);
      f['jet'] = .12 + .88 * power;
      light = .5 * power * stutter;
      core = .45 * power;
      smoke = _hold(t, .16, .45, .82, 1);
      sparks = .25 * pulse(t, .08, .46);
      p.smile = 0;
      p.focus = 0;
      p.sad = fail;
      p.eyeY = 1 - .7 * fail;
      p.brow = -.28 * fail;
  }
  p.aura = 0; // Avoid the common solid disc covering Volt's reactor detail.
  return VoltFrame(
    action: action,
    t: t,
    coilGlow: unit(light),
    coreGlow: unit(core),
    charge: charge,
    discharge: discharge,
    shield: shield,
    trail: trail,
    shockwave: wave,
    flash: flash,
    smoke: smoke,
    sparks: sparks,
    power: power,
  );
}

/// An interrupted touch blends all actuators as well as the visible body.
/// The common blend intentionally does not know these Volt-specific channels.
void blendVoltPose(GamePose pose, GamePose previous, double weight) {
  final w = smooth(weight);
  pose.blendFrom(previous, w);
  for (final key in [
    'joint0',
    'joint1',
    'joint2',
    'joint3',
    'joint4',
    'joint5',
    'joint6',
    'jet',
  ]) {
    pose.extra[key] =
        previous.extra[key]! + (pose.extra[key]! - previous.extra[key]!) * w;
  }
}

void voltTrackGaze(GamePose pose, Offset gaze, {double weight = 1}) {
  pose.head += (gaze.dx * .022).clamp(-.24, .24) * weight;
  pose.headY += gaze.dy.clamp(-8, 8) * .45 * weight;
}

Offset _rot(Offset point, double angle) => Offset(
  point.dx * math.cos(angle) - point.dy * math.sin(angle),
  point.dx * math.sin(angle) + point.dy * math.cos(angle),
);

class VoltAnchors {
  const VoltAnchors(this.leftCoil, this.rightCoil, this.core);
  final Offset leftCoil, rightCoil, core;
}

/// [origin] is the Robot root, i.e. actor.center / floor+(pose.y-126)*scale.
/// Both lightning emitters follow actual articulated coil tips, including
/// mirroring and root rotation. Effects therefore stay attached during flight.
VoltAnchors voltAnchors(
  GamePose pose,
  Offset origin,
  double scale, {
  double facing = 1,
  double coilX = 76,
  double coilY = -60,
  double coilLength = 55,
}) {
  Offset world(Offset point) {
    final local = _rot(point, pose.rotation);
    return origin + Offset(local.dx * scale * facing, local.dy * scale);
  }

  Offset coil(int side) => world(
    Offset(side * coilX, coilY) +
        _rot(
          Offset(0, -coilLength),
          pose.extra[side < 0 ? 'joint0' : 'joint1']!,
        ),
  );
  return VoltAnchors(
    coil(-1),
    coil(1),
    world(_rot(Offset(0, 6), pose.body) + Offset(0, pose.bodyY)),
  );
}

/// At most 8 bolts × 12 segments; no particles, timers, saveLayer or blur
/// filters are allocated. Reduced effects keep the discharge readable with
/// fewer branches and no screen wash, idle sparks or smoke.
void paintVoltEffects(
  Canvas canvas,
  VoltFrame frame,
  VoltAnchors anchors,
  Offset target,
  double ground,
  double scale, {
  bool reduced = false,
  double facing = 1,
}) {
  if (scale <= 0 || !scale.isFinite) return;
  const cyan = Color(0xFF45DFFF), white = Color(0xFFE8FCFF);
  final t = frame.t;
  final paint = Paint()..strokeCap = StrokeCap.round;
  void line(
    Offset a,
    Offset b,
    double width,
    double opacity, [
    Color color = cyan,
  ]) {
    if (opacity <= 0) return;
    canvas.drawLine(
      a,
      b,
      paint
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(.6, width * scale)
        ..color = color.withValues(alpha: unit(opacity)),
    );
  }

  void ring(
    Offset center,
    double radius,
    double opacity, {
    double squash = 1,
    double width = 2,
  }) {
    if (radius <= 0 || opacity <= 0) return;
    canvas.drawOval(
      Rect.fromCenter(
        center: center,
        width: radius * 2 * scale,
        height: radius * 2 * scale * squash,
      ),
      paint
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(.6, width * scale)
        ..color = cyan.withValues(alpha: unit(opacity)),
    );
  }

  void glow(Offset center, double radius, double strength) {
    if (strength <= .01) return;
    canvas.drawCircle(
      center,
      radius * scale,
      paint
        ..style = PaintingStyle.fill
        ..color = cyan.withValues(alpha: .13 * strength),
    );
    canvas.drawCircle(
      center,
      radius * .42 * scale,
      paint..color = white.withValues(alpha: .75 * strength),
    );
  }

  void bolt(
    Offset from,
    Offset to,
    double intensity,
    int seed, {
    double width = 2.4,
    double spread = 8,
    double bow = 0,
  }) {
    if (intensity <= .01) return;
    final path = Path()..moveTo(from.dx, from.dy);
    final delta = to - from;
    final normal = delta.distance < .001
        ? const Offset(0, 1)
        : Offset(-delta.dy, delta.dx) / delta.distance;
    final steps = reduced ? 6 : 12;
    for (var i = 1; i <= steps; i++) {
      final u = i / steps;
      final point =
          Offset.lerp(from, to, u)! +
          normal *
              (math.sin(i * 2.71 + t * 91 + seed * 3.1) *
                  spread *
                  scale *
                  math.sin(u * math.pi)) +
          Offset(0, -bow * scale * math.sin(u * math.pi));
      path.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(
      path,
      paint
        ..style = PaintingStyle.stroke
        ..strokeWidth = (width + 3) * scale
        ..color = cyan.withValues(alpha: .16 * intensity),
    );
    canvas.drawPath(
      path,
      paint
        ..strokeWidth = width * scale
        ..color = cyan.withValues(alpha: .9 * intensity),
    );
    canvas.drawPath(
      path,
      paint
        ..strokeWidth = math.max(.6, width * .32 * scale)
        ..color = white.withValues(alpha: unit(intensity)),
    );
  }

  final left = anchors.leftCoil, right = anchors.rightCoil;
  final mid = Offset.lerp(left, right, .5)!;
  final crown =
      mid +
      Offset(
        0,
        -(frame.action == 'ultimate'
                ? 38
                : frame.action == 'special'
                ? 20
                : 0) *
            scale,
      );
  glow(left, 15 + frame.charge * 7, frame.coilGlow);
  glow(right, 15 + frame.charge * 7, frame.coilGlow);
  glow(anchors.core, 21 + frame.charge * 11, frame.coreGlow);
  if (frame.charge > .02) {
    bolt(
      left,
      right,
      frame.charge,
      0,
      width: frame.action == 'ultimate' ? 3.5 : 2,
      bow: frame.action == 'ultimate'
          ? 38
          : frame.action == 'special'
          ? 20
          : 0,
    );
    if (frame.action == 'charge') {
      bolt(mid, anchors.core, frame.charge * .8, 5, width: 1.8);
      for (var i = 0; i < (reduced ? 1 : 3); i++) {
        final phase = (t * 2 + i / 3) % 1;
        ring(
          anchors.core,
          38 * (1 - phase),
          frame.charge * phase * .65,
          squash: .55,
          width: 1.5,
        );
      }
    }
  }
  if (frame.discharge > .02) {
    final storm = frame.action == 'ultimate';
    final start = frame.action == 'attack' || frame.action == 'quick'
        ? right
        : crown;
    bolt(
      start,
      target,
      frame.discharge,
      1,
      width: storm ? 5 : 2.7,
      spread: storm ? 17 : 8,
    );
    if (storm || frame.action == 'special') {
      // Both articulated masts feed a node above the visor; the face stays
      // readable instead of being crossed by a generic muzzle-to-target beam.
      bolt(
        left,
        crown,
        frame.discharge * .8,
        2,
        width: storm ? 3 : 1.8,
        bow: 8,
      );
      bolt(
        right,
        crown,
        frame.discharge * .8,
        3,
        width: storm ? 3 : 1.8,
        bow: 8,
      );
      glow(crown, storm ? 16 : 10, frame.discharge);
    }
    if (storm && !reduced) {
      for (var i = 0; i < 3; i++) {
        final end =
            target +
            Offset((i - 1) * 36 * scale, (i.isEven ? -1 : 1) * 22 * scale);
        bolt(
          crown + Offset((i - 1) * 16 * scale, -20 * scale),
          end,
          frame.discharge * .72,
          6 + i,
          width: 2.5,
          spread: 18,
        );
      }
    }
    glow(target, storm ? 39 : 17, frame.discharge);
    ring(
      target,
      (storm ? 45 : 21) * frame.discharge,
      frame.discharge * .8,
      width: storm ? 3 : 1.5,
    );
  }
  if (frame.shield > .01) {
    final center = anchors.core + Offset(0, -18 * scale);
    final radius = 110 * frame.shield;
    canvas.drawOval(
      Rect.fromCenter(
        center: center,
        width: radius * 2 * scale,
        height: radius * 2.15 * scale,
      ),
      paint
        ..style = PaintingStyle.fill
        ..color = cyan.withValues(alpha: .06 * frame.shield),
    );
    ring(center, radius, frame.shield * .75, squash: 1.08, width: 2.2);
    final count = reduced ? 2 : 5;
    for (var i = 0; i < count; i++) {
      final angle = i * math.pi * 2 / count + t * 3;
      final a =
          center +
          Offset(math.cos(angle), math.sin(angle) * 1.08) * radius * scale;
      final b =
          center +
          Offset(math.cos(angle + .42), math.sin(angle + .42) * 1.08) *
              radius *
              scale;
      bolt(a, b, frame.shield * .7, i, width: 1.2, spread: 3);
    }
  }
  if (frame.trail > .01) {
    for (var i = 0; i < (reduced ? 2 : 4); i++) {
      final point =
          anchors.core +
          Offset(-facing * (28 + i * 16) * scale, (i - 1.5) * 10 * scale);
      line(
        point,
        point + Offset(-facing * (20 + i * 4) * scale, 0),
        2.5 - i * .35,
        frame.trail * (.65 - i * .12),
      );
    }
  }
  if (frame.shockwave > 0) {
    ring(
      Offset(target.dx, ground),
      20 + 155 * frame.shockwave,
      (1 - frame.shockwave) * .85,
      squash: .3,
      width: 4 * (1 - frame.shockwave) + 1,
    );
    if (!reduced)
      ring(
        Offset(target.dx, ground),
        15 + 110 * frame.shockwave,
        (1 - frame.shockwave) * .5,
        squash: .3,
        width: 1.5,
      );
  }
  if (!reduced && frame.flash > .01) {
    canvas.drawCircle(
      target,
      (38 + frame.flash * 65) * scale,
      paint
        ..style = PaintingStyle.fill
        ..color = white.withValues(alpha: .14 * frame.flash),
    );
  }
  if (!reduced && frame.sparks > .01) {
    for (var i = 0; i < 6; i++) {
      final angle = i * math.pi / 3 + t * 5;
      final center = i.isEven ? left : right;
      final direction = Offset(math.cos(angle), math.sin(angle));
      final radial = ((t * 3 + i * .17) % 1);
      final a = center + direction * (12 + 28 * radial) * scale;
      line(
        a,
        a + direction * (7 * scale),
        1.3,
        frame.sparks * (1 - radial) * .8,
        white,
      );
    }
  }
  if (!reduced && frame.smoke > .01) {
    for (var i = 0; i < 4; i++) {
      final age = (t * 1.6 + i * .25) % 1;
      final center =
          anchors.core +
          Offset(
            math.sin(i * 2 + t * 8) * 12 * scale,
            -(12 + age * 68) * scale,
          );
      canvas.drawCircle(
        center,
        (5 + age * 11) * scale,
        paint
          ..style = PaintingStyle.fill
          ..color = const Color(
            0xFF7893AA,
          ).withValues(alpha: frame.smoke * (1 - age) * .27),
      );
    }
  }
}
