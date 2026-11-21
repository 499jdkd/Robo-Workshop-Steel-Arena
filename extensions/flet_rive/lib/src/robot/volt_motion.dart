import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'game_motion.dart';
import 'volt_choreography.dart';
import 'volt_energy.dart';
import 'volt_storm.dart';

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
  'wave': 1.25,
  'playful': .95,
};

class VoltCue {
  const VoltCue(this.at, this.name);
  final double at;
  final String name;
}

/// Original coil sounds, placed at mechanical charge/release milestones.
const voltCues = <String, List<VoltCue>>{
  'attack': [VoltCue(.22, 'volt_pulse'), VoltCue(.90, 'impact')],
  'quick': [
    VoltCue(.12, 'deploy'),
    VoltCue(.26, 'volt_pulse'),
    VoltCue(.90, 'impact'),
  ],
  'special': [
    VoltCue(.05, 'volt_charge'),
    VoltCue(.46, 'ion'),
    VoltCue(.90, 'impact'),
  ],
  'guard': [VoltCue(.14, 'shield')],
  'dodge': [VoltCue(.16, 'volt_pulse')],
  'charge': [VoltCue(.15, 'volt_charge'), VoltCue(.52, 'repair')],
  'ultimate': [
    VoltCue(.04, 'volt_charge'),
    VoltCue(.31, 'ion'),
    // SceneAudio seeks to the recording's strike; this stays synchronous at
    // every arena speed without introducing a fixed wall-clock delay.
    VoltCue(.62, 'volt_storm'),
    VoltCue(.90, 'impact'),
  ],
  'victory': [VoltCue(.08, 'victory'), VoltCue(.48, 'volt_pulse')],
  'defeat': [VoltCue(.12, 'volt_shutdown')],
  'jump': [VoltCue(.18, 'deploy')],
  'surprise': [VoltCue(.16, 'volt_pulse')],
  'wave': [VoltCue(.08, 'robot_reply_electric'), VoltCue(.42, 'robot_servo')],
  'playful': [VoltCue(.32, 'electric')],
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
    this.shieldHit = 0,
    this.camera = 0,
    this.cameraZoom = 0,
    this.energyField = 0,
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
      power,
      shieldHit,
      camera,
      cameraZoom,
      energyField;
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
  double? guardImpact,
}) {
  final t = normalizedT.isFinite ? unit(normalizedT) : 0.0;
  final idle = .5 + .5 * math.sin(clock * 3.2);
  var light = .32 + .07 * idle, core = .38 + .08 * idle;
  var charge = 0.0, discharge = 0.0, shield = 0.0, trail = 0.0;
  var wave = 0.0, flash = 0.0, smoke = 0.0, sparks = 0.0, power = 1.0;
  final f = p.extra;
  final baseX = p.x, baseY = p.y, baseHeadY = p.headY, baseBodyY = p.bodyY;
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
      p.mode = t < .22 ? 4 : 2;
      f['joint2'] = .55 * load;
      f['joint3'] = -.85 * load;
      f['joint5'] = -.12 * load;
      f['joint6'] = .12 * load;
      charge = load;
      discharge = _hold(t, .22, .26, .90, 1);
      light += .6 * load + .55 * discharge;
      core += .4 * load;
      p.focus = load;
      p.smile = 1 - load;
    case 'quick':
      final dash = _hold(t, .12, .28, .4, .83);
      p.mode = 2;
      f['joint2'] = .7 * dash;
      f['joint3'] = -.7 * dash;
      f['jet'] = 1 + .7 * dash;
      discharge = _hold(t, .26, .3, .87, 1);
      trail = dash;
      light += .7 * discharge;
      core += .45 * dash;
      p.eyeY = 1 - .25 * dash;
      p.focus = dash;
      p.smile = 1 - dash;
    case 'special':
      final load = _hold(t, 0, .38, .46, .8);
      p.mode = t < .46 ? 4 : 2;
      f['joint2'] = .92 * load;
      f['joint3'] = -.92 * load;
      f['joint4'] = clock * .35 + 2.5 * load;
      f['joint5'] = -.3 * load;
      f['joint6'] = .3 * load;
      charge = load;
      discharge = _hold(t, .46, .5, .89, 1);
      light += .8 * load;
      core += .65 * load;
      p.focus = load;
      p.smile = 1 - load;
      p.eyeY = 1 - .3 * load;
    case 'guard':
      final hold = _hold(t, 0, .2, .86, 1);
      p.mode = 3;
      f['joint2'] = .85 * hold;
      f['joint3'] = -.85 * hold;
      p.shield = 0; // The electrical shell has its own bounded painter.
      shield = hold;
      light += .55 * hold;
      core += .35 * hold;
      p.focus = hold;
      p.smile = 1 - hold;
    case 'dodge':
      final dash = _hold(t, .14, .3, .48, .94);
      p.mode = 1;
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
      final storm = VoltStorm(t);
      final flight = _hold(t, .1, .34, .74, 1);
      final open = _hold(t, .17, .44, .76, .99);
      p.mode = t < .62 ? 4 : 2;
      f['joint2'] = 1.35 * open;
      f['joint3'] = -1.35 * open;
      f['joint4'] = clock * .35 + 13 * t * open;
      f['joint5'] = -.85 * open;
      f['joint6'] = .85 * open;
      f['jet'] = 1 + .8 * flight;
      charge = storm.charge;
      discharge = storm.discharge;
      light += .9 * open;
      core += .9 * charge;
      wave = t > .88 && t < 1 ? _ring(t, .88, 1) : 0;
      flash = storm.ignition;
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
      final airborne = pulse(t, .18, .78);
      final land = pulse(t, .78, 1);
      p.mode = 6;
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
    case 'wave':
      final greet = _hold(t, 0, .17, .72, 1);
      p.y -= 4 * greet;
      p.head = -.15 * greet;
      p.body = .08 * greet;
      p.armR = -1.45 * greet - .1;
      p.foreR = (.65 + .5 * math.sin(t * math.pi * 7)) * greet;
      p.armL = .1 + .3 * greet;
      p.eyeY = 1 - .2 * greet;
      f['joint1'] = .18 * math.sin(t * math.pi * 4) * greet;
      light += .2 * greet;
    case 'playful':
      final aim = _hold(t, 0, .22, .48, 1);
      final ping = pulse(t, .3, .48);
      p.head = -.2 * aim + .1 * ping;
      p.body = -.1 * aim;
      p.armR = -.1 - .8 * aim;
      p.foreR = .5 * aim;
      p.armL = .1 + .45 * aim;
      f['joint1'] = -.55 * aim + .18 * ping;
      f['joint3'] = -.5 * aim;
      light += .5 * aim;
      sparks = .35 * ping;
      p.smile = 1;
    case 'victory':
      final cheer = _hold(t, 0, .16, .82, 1);
      p.mode = 6;
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
      f['joint2'] = .35 * (1 - fail);
      f['joint3'] = -.35 * (1 - fail);
      f['joint4'] = math.sin(t * 9) * .35 * (1 - fail);
      f['joint5'] = -.1 * (1 - fail);
      f['joint6'] = .1 * (1 - fail);
      f['jet'] = .12 + .88 * power;
      light = .5 * power * stutter;
      core = .45 * power * (.6 + .4 * stutter);
      smoke = _hold(t, .16, .45, .82, 1);
      sparks = .25 * pulse(t, .08, .46);
      p.smile = 0;
      p.focus = 0;
      p.sad = fail;
      p.eyeY = 1 - .7 * fail;
      p.brow = -.28 * fail;
  }
  applyVoltChoreography(
    p,
    action,
    t,
    baseX: baseX,
    baseY: baseY,
    baseHeadY: baseHeadY,
    baseBodyY: baseBodyY,
  );
  final emitter =
      {'attack', 'quick', 'special', 'ultimate', 'playful'}.contains(action)
      ? unit(math.max(charge, discharge))
      : 0.0;
  f['voltEmitterTravel'] = -6 - (action == 'ultimate' ? 18 : 12) * emitter;
  if (action == 'ultimate') {
    final pressure = VoltStorm(t).pressure;
    f['joint0'] = f['joint0']! + .025 * pressure * math.sin(clock * 43);
    f['joint1'] = f['joint1']! - .025 * pressure * math.sin(clock * 43 + .4);
  }
  f['voltEmitterGlow'] = emitter * power;
  f['voltEmitterAimR'] =
      (action == 'attack'
          ? 1.4
          : action == 'quick'
          ? 1.05
          : 0) *
      emitter;
  f['voltEmitterAimL'] = action == 'attack' ? -.2 * emitter : 0;
  final hit = action == 'guard'
      ? unit(guardImpact ?? .9 * pulse(t, .47, .69))
      : 0.0;
  if (hit > 0) {
    p.x -= 8 * hit;
    p.body -= .16 * hit;
    p.head += .12 * hit;
    p.foreL -= .14 * hit;
    p.foreR += .17 * hit;
    f['joint0'] = f['joint0']! - .12 * hit;
    f['joint1'] = f['joint1']! + .15 * hit;
    f['voltPistonL'] = f['voltPistonL']! - 2 * hit;
    f['voltPistonR'] = f['voltPistonR']! - 2 * hit;
    light += .25 * hit;
  }
  // The detailed optical iris, brow actuator, counter-rotor and radiator
  // shutters are independent of the head/body/coil mechanisms above.
  f['joint7'] = -f['joint4']! * .77;
  f['joint10'] =
      (.6 * (1 - unit(p.eyeY)) + .25 * unit(p.focus) + .28 * (1 - power)).clamp(
        0.0,
        .7,
      );
  f['joint11'] = (p.brow * .45 - .04 * p.shock).clamp(-.25, .25);
  final ventilation = unit(charge * .75 + discharge * .5 + wave * .2);
  f['joint12'] = -.5 * ventilation * power;
  f['joint13'] = .5 * ventilation * power * (.94 + .06 * math.sin(clock * 3));
  p.aura = 0; // Avoid the common solid disc covering Volt's reactor detail.
  f['voltFacePower'] = power;
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
    shieldHit: hit,
    camera: action == 'ultimate'
        ? unit(discharge * .8 + flash * .75 + VoltStorm(t).arrival * .65)
        : hit * .2,
    cameraZoom: action == 'ultimate' ? unit((baseY - p.y) / 83) : 0,
    energyField: action == 'ultimate' ? .95 * VoltStorm(t).charge : 0,
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
    'joint7',
    'joint8',
    'joint9',
    'joint10',
    'joint11',
    'joint12',
    'joint13',
    'joint14',
    'joint15',
    'jet',
    'voltEmitterGlow',
    ...voltMechanismDefaults.keys,
  ]) {
    final old = previous.extra[key] ?? voltMechanismDefaults[key] ?? 0;
    var delta = pose.extra[key]! - old;
    if (key == 'joint4' || key == 'joint7') {
      delta = (delta + math.pi) % (math.pi * 2) - math.pi;
    }
    pose.extra[key] = old + delta * w;
  }
}

double voltBlendSeconds(String action) => switch (action) {
  'quick' => .055,
  'attack' => .075,
  'dodge' => .065,
  'surprise' => .07,
  'guard' => .10,
  'ultimate' => .18,
  'defeat' => .22,
  _ => .14,
};

VoltFrame blendVoltFrame(VoltFrame next, VoltFrame? before, double weight) {
  if (before == null || weight >= 1) return next;
  final w = smooth(weight);
  double mix(double a, double b) => a + (b - a) * w;
  return VoltFrame(
    action: next.action,
    t: next.t,
    coilGlow: mix(before.coilGlow, next.coilGlow),
    coreGlow: mix(before.coreGlow, next.coreGlow),
    charge: mix(before.charge, next.charge),
    discharge: mix(before.discharge, next.discharge),
    shield: mix(before.shield, next.shield),
    trail: mix(before.trail, next.trail),
    shockwave: mix(before.shockwave, next.shockwave),
    flash: mix(before.flash, next.flash),
    smoke: mix(before.smoke, next.smoke),
    sparks: mix(before.sparks, next.sparks),
    power: mix(before.power, next.power),
    shieldHit: mix(before.shieldHit, next.shieldHit),
    camera: mix(before.camera, next.camera),
    cameraZoom: mix(before.cameraZoom, next.cameraZoom),
    energyField: mix(before.energyField, next.energyField),
  );
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
  const VoltAnchors(
    this.leftCoil,
    this.rightCoil,
    this.core, {
    Offset? leftEmitter,
    Offset? rightEmitter,
  }) : leftEmitter = leftEmitter ?? leftCoil,
       rightEmitter = rightEmitter ?? rightCoil;
  final Offset leftCoil, rightCoil, core, leftEmitter, rightEmitter;
}

/// The large charge stays in front of the visor and within a phone scene.
Offset voltStormCenter(
  VoltAnchors anchors,
  VoltFrame frame,
  double scale, {
  double facing = 1,
  Rect? viewport,
}) {
  final mid = Offset.lerp(anchors.leftEmitter, anchors.rightEmitter, .5)!;
  final inset = VoltStorm.boundsRadius * scale + 8;
  var x = mid.dx + facing * (42 + 104 * frame.cameraZoom) * scale;
  var y = math.max(mid.dy - 28 * scale, (viewport?.top ?? 0) + inset);
  if (viewport != null) {
    x = viewport.width > inset * 2
        ? x.clamp(viewport.left + inset, viewport.right - inset)
        : viewport.center.dx;
    y = viewport.height > inset * 2
        ? y.clamp(viewport.top + inset, viewport.bottom - inset)
        : viewport.center.dy;
  }
  return Offset(x, y);
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
  Offset emitter(int side) {
    final crown =
        Offset(0, -coilLength) +
        _rot(
          _rot(
            Offset(0, (pose.extra['voltEmitterTravel'] ?? -6) - 2),
            pose.extra[side < 0 ? 'voltEmitterAimL' : 'voltEmitterAimR'] ?? 0,
          ),
          pose.extra[side < 0 ? 'joint2' : 'joint3'] ?? 0,
        );
    return world(
      Offset(side * coilX, coilY) +
          _rot(crown, pose.extra[side < 0 ? 'joint0' : 'joint1'] ?? 0),
    );
  }

  return VoltAnchors(
    coil(-1),
    coil(1),
    world(_rot(Offset(0, 6), pose.body) + Offset(0, pose.bodyY)),
    leftEmitter: emitter(-1),
    rightEmitter: emitter(1),
  );
}

/// A pair of analytic outlines make a short displacement visible on a phone.
/// They are lightweight motion echoes, not repeated recordings of the model.
void paintVoltMotionEchoes(
  Canvas canvas,
  VoltFrame frame,
  Offset origin,
  double scale, {
  double facing = 1,
  bool reduced = false,
}) {
  if (reduced ||
      scale <= 0 ||
      !scale.isFinite ||
      frame.trail <= .04 ||
      !{'quick', 'dodge'}.contains(frame.action))
    return;
  final direction = frame.action == 'dodge' ? -facing : facing;
  final energy = VoltEnergyPainter(canvas, scale, frame.t);
  for (var i = 2; i >= 1; i--) {
    final center =
        origin + Offset(-direction * (30 + i * 28) * scale, i * 3 * scale);
    final alpha = frame.trail * (.24 - i * .055);
    final head = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: center + Offset(0, -85 * scale),
        width: 107 * scale,
        height: 77 * scale,
      ),
      Radius.circular(20 * scale),
    );
    final body = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: center + Offset(0, 8 * scale),
        width: 125 * scale,
        height: 112 * scale,
      ),
      Radius.circular(27 * scale),
    );
    final paint = Paint()
      ..style = PaintingStyle.fill
      ..color = VoltEnergyPainter.cyan.withValues(alpha: alpha * .45);
    canvas.drawRRect(head, paint);
    canvas.drawRRect(body, paint);
    paint
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(1, 2 * scale)
      ..color = VoltEnergyPainter.cyan.withValues(alpha: alpha);
    canvas.drawRRect(head, paint);
    canvas.drawRRect(body, paint);
    for (final side in [-1, 1]) {
      energy.line(
        center + Offset(side * 76, -105) * scale,
        center + Offset(side * 76, -43) * scale,
        9,
        VoltEnergyPainter.cyan,
        alpha,
      );
      energy.line(
        center + Offset(side * 43, 73) * scale,
        center + Offset(side * 43 - direction * 17, 91) * scale,
        7,
        VoltEnergyPainter.cyan,
        alpha,
      );
    }
  }
}

/// At most 8 bolts of 12 segments plus bounded beam/orb paths; no extra timers,
/// saveLayer or blur
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
  bool preview = false,
  Rect? viewport,
}) {
  if (scale <= 0 || !scale.isFinite) return;
  const cyan = Color(0xFF45DFFF), white = Color(0xFFE8FCFF);
  final t = frame.t;
  final energy = VoltEnergyPainter(canvas, scale, t, reduced: reduced);
  final paint = Paint()..strokeCap = StrokeCap.round;
  var boltBudget = reduced ? 4 : 8;
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

  void bolt(
    Offset from,
    Offset to,
    double intensity,
    int seed, {
    double width = 2.4,
    double spread = 8,
    double bow = 0,
  }) {
    if (intensity <= .01 || boltBudget <= 0) return;
    boltBudget--;
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

  final left = anchors.leftEmitter, right = anchors.rightEmitter;
  final storm = frame.action == 'ultimate';
  final skill = frame.action == 'special';
  final mid = Offset.lerp(left, right, .5)!;
  // Fit the complete capacitor inside a short phone scene during flight.
  final crown = storm
      ? voltStormCenter(
          anchors,
          frame,
          scale,
          facing: facing,
          viewport: viewport,
        )
      : Offset(
          mid.dx,
          math.max(
            mid.dy - (skill ? 34 : 0) * scale,
            (skill ? 46 : 0) * scale + 8,
          ),
        );
  final flight = unit(
    (t -
            (storm
                ? .62
                : skill
                ? .46
                : .22)) /
        (.9 -
            (storm
                ? .62
                : skill
                ? .46
                : .22)),
  );
  final impact = pulse(t, .86, 1);
  if (frame.energyField > .01) {
    for (var i = 0; i < (reduced ? 1 : 3); i++) {
      final u = (t * 2 + i / 3) % 1;
      ring(
        anchors.core + Offset(0, (u - .5) * 160 * scale),
        126 + 18 * math.sin(u * math.pi),
        frame.energyField * .7 * math.sin(u * math.pi),
        squash: .38,
        width: 2.8,
      );
    }
  }
  if (frame.charge > .02) {
    energy.transfer(anchors.core, left, right, frame.charge * .8);
    if (storm || skill) {
      bolt(left, crown, frame.charge, 0, width: storm ? 6.5 : 2.8, bow: 12);
      bolt(right, crown, frame.charge, 1, width: storm ? 6.5 : 2.8, bow: 12);
      if (!skill) energy.capacitor(crown, frame.charge, storm: storm);
    } else {
      bolt(left, right, frame.charge * .7, 0, width: 2.4);
    }
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
  if (skill) energy.skillLens(crown, frame.charge, frame.discharge);
  if (frame.action == 'attack' || frame.action == 'quick') {
    energy.muzzle(
      right,
      frame.charge,
      frame.discharge * (1 - flight * .6),
      facing,
    );
  }
  if (frame.action == 'quick') {
    energy.dashContact(
      anchors.core + Offset(facing * 84, -18) * scale,
      frame.trail * (1 - _ramp(t, .48, .85)),
      facing,
    );
  }
  if (frame.discharge > .02) {
    if (frame.action == 'attack') {
      energy.pulse(right, target, flight, frame.discharge);
    } else if (frame.action == 'quick') {
      energy.pulse(
        right,
        target,
        unit((t - .42) / .48),
        frame.discharge * _ramp(t, .4, .48),
      );
    } else if (storm || skill) {
      if (skill) {
        energy.skillBeam(crown, target, _ramp(t, .46, .76), frame.discharge);
      } else {
        energy.beam(
          crown,
          target,
          storm ? VoltStorm(t).extension : _ramp(t, .46, .89),
          frame.discharge,
          storm: storm,
        );
      }
      bolt(
        left,
        crown,
        frame.discharge * .85,
        2,
        width: storm ? 6 : 2.5,
        bow: 10,
      );
      bolt(
        right,
        crown,
        frame.discharge * .85,
        3,
        width: storm ? 6 : 2.5,
        bow: 10,
      );
      if (storm) {
        final blast = VoltStorm(t).ignition;
        energy.impact(crown, blast, unit((t - .62) / .15), storm: true);
        if (!reduced) {
          for (var i = 0; i < 3; i++) {
            bolt(
              crown,
              Offset.lerp(crown, target, flight)! +
                  Offset((i - 1) * 34, (i.isEven ? -1 : 1) * 25) * scale,
              frame.discharge * .8,
              6 + i,
              width: 3.6,
              spread: 19,
            );
          }
        }
      }
    } else {
      bolt(right, target, frame.discharge, 1, width: 3.2);
    }
    if ({'attack', 'quick', 'special', 'ultimate'}.contains(frame.action)) {
      energy.impact(
        target,
        impact * frame.discharge,
        unit((t - .86) / .14),
        storm: storm,
      );
    }
  }
  if (frame.shield > .01) {
    energy.shield(
      anchors.core + Offset(0, -18 * scale),
      frame.shield,
      frame.shieldHit,
      facing,
      preview: preview,
    );
  }
  if (frame.trail > .01) {
    for (var i = 0; i < (reduced ? 2 : 4); i++) {
      final point =
          anchors.core +
          Offset(
            -facing *
                (frame.action == 'dodge' ? -1 : 1) *
                (28 + i * 16) *
                scale,
            (i - 1.5) * 10 * scale,
          );
      line(
        point,
        point +
            Offset(
              -facing *
                  (frame.action == 'dodge' ? -1 : 1) *
                  (20 + i * 4) *
                  scale,
              0,
            ),
        2.5 - i * .35,
        frame.trail * (.65 - i * .12),
      );
    }
  }
  if (frame.shockwave > 0) {
    ring(
      Offset(target.dx, ground),
      20 + (storm ? 260 : 155) * frame.shockwave,
      (1 - frame.shockwave) * .85,
      squash: .3,
      width: 4 * (1 - frame.shockwave) + 1,
    );
    if (!reduced)
      ring(
        Offset(target.dx, ground),
        15 + (storm ? 195 : 110) * frame.shockwave,
        (1 - frame.shockwave) * .5,
        squash: .3,
        width: 1.5,
      );
  }
  if (!reduced && frame.flash > .01) {
    canvas.drawCircle(
      target,
      (storm ? 70 + frame.flash * 145 : 38 + frame.flash * 65) * scale,
      paint
        ..style = PaintingStyle.fill
        ..color = white.withValues(alpha: (storm ? .18 : .14) * frame.flash),
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
