import 'dart:math' as math;
import 'package:material_ui/material_ui.dart';
import 'game_motion.dart';
import 'volt_motion.dart' show VoltFrame, VoltCue;

// The presentation envelope is shared; Titan owns every pose, mechanism, cue
// and effect. No Volt timeline or electrical effect is sampled here.
const titanActionSeconds = <String, double>{
  'attack': 1.25,
  'quick': 1.05,
  'special': 2.4,
  'guard': 1.5,
  'dodge': 1.0,
  'charge': 1.8,
  'ultimate': 3.35,
  'victory': 2.7,
  'defeat': 3.0,
  'joy': 1.4,
  'jump': 1.6,
  'surprise': 1.3,
  'anger': 1.5,
  'dance': 3.0,
  'inspect': 1.9,
  'wave': 1.5,
  'playful': 1.4,
  'feed': 1.7,
};
const titanCues = <String, List<VoltCue>>{
  'attack': [VoltCue(.08, 'titan_hydraulic'), VoltCue(.9, 'titan_ram')],
  'quick': [
    VoltCue(.1, 'titan_hydraulic'),
    VoltCue(.2, 'titan_step'),
    VoltCue(.36, 'titan_ram'),
    VoltCue(.54, 'impact'),
    VoltCue(.72, 'titan_ram'),
    VoltCue(.9, 'impact'),
  ],
  'special': [
    VoltCue(.08, 'titan_pressure'),
    VoltCue(.4, 'titan_hydraulic'),
    VoltCue(.46, 'titan_ram'),
    VoltCue(.78, 'impact'),
    VoltCue(.94, 'titan_hydraulic'),
  ],
  'guard': [VoltCue(.14, 'titan_bastion')],
  'dodge': [VoltCue(.16, 'titan_step')],
  'charge': [VoltCue(.12, 'titan_pressure'), VoltCue(.55, 'titan_hydraulic')],
  'ultimate': [
    VoltCue(.04, 'titan_pressure'),
    VoltCue(.35, 'titan_rumble'),
    VoltCue(.66, 'titan_quake'),
    VoltCue(.9, 'titan_ram'),
  ],
  'victory': [
    VoltCue(.08, 'victory'),
    VoltCue(.32, 'titan_ram'),
    VoltCue(.62, 'titan_step'),
  ],
  'defeat': [VoltCue(.08, 'titan_shutdown')],
  'jump': [VoltCue(.18, 'titan_hydraulic'), VoltCue(.72, 'titan_step')],
  'joy': [VoltCue(.2, 'robot_reply_heavy')],
  'dance': [
    VoltCue(.14, 'titan_step'),
    VoltCue(.4, 'robot_dance_bass'),
    VoltCue(.72, 'titan_step'),
  ],
  'anger': [VoltCue(.22, 'robot_grump'), VoltCue(.56, 'titan_step')],
  'surprise': [VoltCue(.12, 'robot_surprise')],
  'wave': [VoltCue(.16, 'robot_reply_heavy')],
  'inspect': [VoltCue(.2, 'titan_hydraulic')],
  'playful': [VoltCue(.4, 'titan_ram')],
};
Iterable<String> titanCuesCrossed(
  String name,
  double before,
  double after,
) sync* {
  if (!before.isFinite || !after.isFinite || after < before) return;
  for (final cue in titanCues[name] ?? const <VoltCue>[])
    if (before < cue.at && after >= cue.at) yield cue.name;
}

class TitanKey {
  const TitanKey(
    this.t, {
    this.x = 0,
    this.y = 0,
    this.body = 0,
    this.head = 0,
    this.l = .08,
    this.r = -.08,
    this.el = 0,
    this.er = 0,
    this.hammer = 0,
    this.stance = 0,
    this.tuck = 0,
  });
  final double t, x, y, body, head, l, r, el, er, hammer, stance, tuck;
}

const titanKeys = <String, List<TitanKey>>{
  'feed': [
    TitanKey(0),
    TitanKey(.18, y: 7, head: -.15, r: 1.1, er: .9),
    TitanKey(.4, y: 1, head: .12, r: 1.3, er: 1.4),
    TitanKey(.63, y: 5, head: -.08, r: 1.25, er: 1.2),
    TitanKey(.84, head: .06, r: .4, er: .5),
    TitanKey(1),
  ],
  'attack': [
    TitanKey(0),
    TitanKey(.16, x: -14, y: 10, body: -.17, r: .55, er: .7, stance: 1),
    TitanKey(.22, x: -10, y: 7, r: -.9, er: .2, stance: 1),
    TitanKey(.44, x: 18, body: .18, r: -1.5, er: -.05, stance: 1),
    TitanKey(.88, x: 22, y: 3, body: .21, r: -1.5, er: -.05, stance: 1),
    TitanKey(.93, x: 9, y: 6, body: .1, r: -1.25, er: .18, stance: 1),
    TitanKey(1),
  ],
  'quick': [
    TitanKey(0),
    TitanKey(.16, x: -15, y: 16, body: -.14, l: -.5, r: -.6, stance: 1),
    TitanKey(.26, x: 14, y: 8, l: -.9, r: -1.3, stance: 1),
    TitanKey(.36, x: 26, y: 4, body: .18, l: -.8, r: -1.6, stance: 1),
    TitanKey(.54, x: 20, y: 8, body: -.16, l: -1.6, r: -.8, stance: 1),
    TitanKey(.72, x: 28, y: 4, body: .2, l: -.8, r: -1.6, stance: 1),
    TitanKey(.9, x: 22, y: 8, body: -.17, l: -1.6, r: -.8, stance: 1),
    TitanKey(1),
  ],
  'special': [
    TitanKey(0),
    TitanKey(.14, x: -8, y: 11, body: -.12, l: -.4, r: -.8, er: .3, stance: 1),
    TitanKey(.35, x: -12, y: 8, l: -.55, r: -1.5, er: -.04, stance: 1),
    TitanKey(
      .46,
      x: -16,
      y: 10,
      body: -.12,
      l: -.55,
      r: -1.5,
      er: -.04,
      stance: 1,
    ),
    TitanKey(.54, x: -5, y: 6, body: .05, l: -.45, r: -1.4, stance: 1),
    TitanKey(.82, x: -4, y: 5, l: -.4, r: -1.4, stance: 1),
    TitanKey(.94, x: -7, y: 8, body: -.07, r: -1.35, er: .15, stance: 1),
    TitanKey(1),
  ],
  'guard': [
    TitanKey(0),
    TitanKey(.2, y: 12, l: .95, r: -.95, el: -1.35, er: 1.35, stance: 1),
    TitanKey(
      .56,
      x: -6,
      y: 14,
      body: -.12,
      l: 1.05,
      r: -1.05,
      el: -1.45,
      er: 1.45,
      stance: 1,
    ),
    TitanKey(.84, y: 9, l: .85, r: -.85, el: -1.25, er: 1.25, stance: 1),
    TitanKey(1),
  ],
  'dodge': [
    TitanKey(0),
    TitanKey(.16, x: 9, y: 18, body: .2, stance: 1),
    TitanKey(
      .38,
      x: -105,
      y: 5,
      body: -.3,
      l: .55,
      r: -1.0,
      el: -.4,
      er: .8,
      stance: 1,
    ),
    TitanKey(.62, x: -70, y: 12, body: -.16, l: .2, r: -.7),
    TitanKey(.9, x: -5, y: 4),
    TitanKey(1),
  ],
  'charge': [
    TitanKey(0),
    TitanKey(.24, y: 10, l: -.9, r: .9, stance: 1),
    TitanKey(
      .7,
      y: 5,
      body: -.07,
      l: -1.15,
      r: 1.15,
      el: .35,
      er: -.35,
      stance: 1,
    ),
    TitanKey(.9, y: 2, l: -.4, r: .4),
    TitanKey(1),
  ],
  'ultimate': [
    TitanKey(0),
    TitanKey(.12, y: 23, l: .5, r: -.5, stance: 1),
    TitanKey(
      .32,
      y: 5,
      body: -.1,
      l: 2.65,
      r: -2.65,
      el: -.4,
      er: .4,
      stance: 1,
    ),
    TitanKey(
      .48,
      y: -56,
      l: 2.9,
      r: -2.9,
      el: -.2,
      er: .2,
      tuck: 13,
      stance: 1,
    ),
    TitanKey(
      .6,
      y: -66,
      body: -.1,
      l: 3.0,
      r: -3.0,
      el: -.1,
      er: .1,
      tuck: 16,
      stance: 1,
    ),
    TitanKey(.66, y: 24, body: .12, l: .12, r: -.12, hammer: 46, stance: 1),
    TitanKey(.81, y: 16, body: .06, l: .15, r: -.15, hammer: 36, stance: 1),
    TitanKey(.94, y: 5, l: .3, r: -.3, hammer: 8, stance: 1),
    TitanKey(1),
  ],
  'victory': [
    TitanKey(0),
    TitanKey(.2, y: 6, l: .1, r: .9, er: -.4),
    TitanKey(.36, y: 1, l: -.9, r: -.1, el: .4),
    TitanKey(.55, y: -8, l: 2.3, r: -2.3, el: -.4, er: .4),
    TitanKey(.78, y: 3, l: 1.1, r: -1.1),
    TitanKey(1),
  ],
  'defeat': [
    TitanKey(0),
    TitanKey(.17, y: 8, body: -.1, l: .3, r: -.2),
    TitanKey(.4, y: 20, body: .17, head: .16, l: -.3, r: .2, el: .3, er: -.3),
    TitanKey(.7, y: 32, body: .24, head: .3, l: -.15, r: .12, hammer: 12),
    TitanKey(1, y: 34, body: .23, head: .32, l: -.12, r: .1, hammer: 16),
  ],
  'joy': [
    TitanKey(0),
    TitanKey(.2, y: 9, l: .5, r: -.5),
    TitanKey(.4, y: -10, l: 1.8, r: -1.8),
    TitanKey(.62, y: 5, l: 1.2, r: -1.2, el: -.8, er: .8),
    TitanKey(.82, y: -3, l: .4, r: -.4),
    TitanKey(1),
  ],
  'jump': [
    TitanKey(0),
    TitanKey(.18, y: 24, l: .6, r: -.6, stance: 1),
    TitanKey(.4, y: -68, l: 1.8, r: -1.8, tuck: 14),
    TitanKey(.58, y: -38, l: 1.1, r: -1.1, tuck: 7),
    TitanKey(.75, y: 23, l: .6, r: -.6, stance: 1),
    TitanKey(.9, y: -3),
    TitanKey(1),
  ],
  'surprise': [
    TitanKey(0),
    TitanKey(.15, y: 17, head: -.2, l: .4, r: -.4),
    TitanKey(.32, y: -8, head: .1, l: 1.25, r: -1.25, el: -.6, er: .6),
    TitanKey(.7, y: 4, head: -.15, l: .5, r: -.5),
    TitanKey(1),
  ],
  'anger': [
    TitanKey(0),
    TitanKey(.2, y: 10, head: -.2, l: .3, r: -.4),
    TitanKey(.45, x: -8, y: 8, head: .2, l: .7, r: -.6),
    TitanKey(.6, x: 5, y: 20, head: -.2, l: .4, r: -.4, stance: 1),
    TitanKey(.8, y: 6, head: .1, l: .3, r: -.3),
    TitanKey(1),
  ],
  'dance': [
    TitanKey(0),
    TitanKey(
      .15,
      x: -17,
      y: 10,
      body: -.15,
      l: 1.5,
      r: -.4,
      el: -.5,
      stance: 1,
    ),
    TitanKey(.32, x: 17, y: 2, body: .16, l: .4, r: -1.5, er: .5, stance: 1),
    TitanKey(.5, x: -18, y: 12, body: -.16, l: 1.7, r: -.5, el: -.7, stance: 1),
    TitanKey(.68, x: 18, y: 2, body: .17, l: .4, r: -1.7, er: .7, stance: 1),
    TitanKey(.86, y: 8, l: 1.3, r: -1.3),
    TitanKey(1),
  ],
  'inspect': [
    TitanKey(0),
    TitanKey(.2, y: 4, head: -.22, r: -1.2, er: .9),
    TitanKey(.55, head: .18, r: -1.5, er: 1.3),
    TitanKey(.8, head: -.1, r: -.6, er: .5),
    TitanKey(1),
  ],
  'wave': [
    TitanKey(0),
    TitanKey(.22, l: 2.2, el: -.5, head: -.1),
    TitanKey(.4, l: 2.5, el: -.8, head: .1),
    TitanKey(.6, l: 2.2, el: -.3),
    TitanKey(.8, l: 1.2),
    TitanKey(1),
  ],
  'playful': [
    TitanKey(0),
    TitanKey(.2, y: 5, head: .15, r: -1.2, er: .8),
    TitanKey(.43, head: -.12, r: -1.6, er: .2, hammer: 16),
    TitanKey(.65, head: .13, r: -1.0, er: .8),
    TitanKey(1),
  ],
};
double _ramp(double t, double a, double b) => smooth((t - a) / (b - a));
double _hold(double t, double a, double b, double c, double d) =>
    _ramp(t, a, b) * (1 - _ramp(t, c, d));

const titanSkillRelease = .46;
const titanSkillImpact = .78;
const titanQuakeRelease = .66;
const titanQuickHits = [.36, .54, .72, .9];

double titanPunchReach(String action, double t, bool left) {
  if (action == 'attack') {
    return left ? 0 : _ramp(t, .22, .9) * (1 - _ramp(t, .915, 1));
  }
  if (action != 'quick') return 0;
  var result = 0.0;
  for (var i = 0; i < titanQuickHits.length; i++) {
    if (left != i.isOdd) continue;
    final hit = titanQuickHits[i];
    result = math.max(
      result,
      _hold(t, hit - .085, hit - .005, hit + .012, hit + .085),
    );
  }
  return result;
}

double titanPunchImpact(String action, double t, bool left) {
  final hits = action == 'quick'
      ? [
          for (var i = 0; i < titanQuickHits.length; i++)
            if (left == i.isOdd) titanQuickHits[i],
        ]
      : action == 'special'
      ? [titanSkillImpact]
      : left
      ? <double>[]
      : [.9];
  var impact = 0.0;
  for (final hit in hits) {
    impact = math.max(
      impact,
      _hold(t, hit - .004, hit + .012, hit + .045, math.min(1, hit + .105)),
    );
  }
  return impact;
}

VoltFrame applyTitanPose(
  GamePose p,
  String action,
  double progress, {
  String equippedWeapon = '',
  double clock = 0,
  double? guardImpact,
}) {
  final t = progress.isFinite ? unit(progress) : 0.0;
  final keys = titanKeys[action] ?? const [TitanKey(0), TitanKey(1)];
  var a = keys.first, b = keys.last;
  for (var i = 1; i < keys.length; i++) {
    if (t <= keys[i].t) {
      a = keys[i - 1];
      b = keys[i];
      break;
    }
  }
  final w = smooth((t - a.t) / math.max(.001, b.t - a.t));
  double mix(double x, double y) => x + (y - x) * w;
  p.x = mix(a.x, b.x);
  p.y = mix(a.y, b.y);
  p.body = mix(a.body, b.body);
  p.head = mix(a.head, b.head) + .018 * math.sin(clock * 1.7);
  p.headY = -112 + 1.5 * math.sin(clock * 1.6);
  p.bodyY = -1.5 * math.sin(clock * 1.9);
  p.armL = mix(a.l, b.l);
  p.armR = mix(a.r, b.r);
  p.foreL = mix(a.el, b.el);
  p.foreR = mix(a.er, b.er);
  p.shield = 0;
  p.aura = 0;
  p.rotation = 0;
  p.weapon = equippedWeapon;
  p.deploy = equippedWeapon.isEmpty ? 0 : .55;
  final heavy = action == 'ultimate', skill = action == 'special';
  final charge = {'special', 'ultimate', 'charge'}.contains(action)
      ? _hold(t, 0, heavy ? .48 : .35, heavy ? .62 : .46, heavy ? .72 : .7)
      : 0.0;
  final release = heavy
      ? .62
      : skill
      ? .46
      : action == 'quick'
      ? .26
      : .22;
  final attack = {
    'attack',
    'quick',
    'special',
    'ultimate',
    'playful',
    'feed',
  }.contains(action);
  final discharge = attack ? _hold(t, release, release + .045, .9, 1) : 0.0;
  final shield = action == 'guard' ? _hold(t, 0, .2, .85, 1) : 0.0;
  final hit = action == 'guard'
      ? unit(guardImpact ?? .9 * pulse(t, .47, .69))
      : 0.0;
  final power = action == 'defeat' ? 1 - _ramp(t, .12, .95) : 1.0;
  if (action == 'defeat') {
    p.head = mix(a.head, b.head) + .018 * math.sin(clock * 1.7) * power;
    p.headY = -112 + 1.5 * math.sin(clock * 1.6) * power;
    p.bodyY = -1.5 * math.sin(clock * 1.9) * power;
  }
  final stance = mix(a.stance, b.stance),
      hammer = mix(a.hammer, b.hammer),
      tuck = mix(a.tuck, b.tuck);
  final f = p.extra;
  f['titanPower'] = power;
  f['titanPress'] = power * (.35 + .65 * math.max(charge, discharge));
  f['joint0'] = .06 * math.sin(clock * 2) * power + p.armL * .12;
  f['joint1'] = -.06 * math.sin(clock * 2 + .4) * power + p.armR * .12;
  f['joint4'] = -2.1 + 4.2 * math.max(charge, discharge * .7);
  f['joint7'] = (clock * .18 + charge * 3) * power;
  f['joint5'] = -.12 - charge * .35;
  f['joint6'] = .12 + charge * .35;
  f['titanVentL'] = -charge * .65;
  f['titanVentR'] = charge * .65;
  f['titanShieldWingL'] = shield * .55;
  f['titanShieldWingR'] = -shield * .55;
  f['titanPistonL'] = 26 + 8 * math.sin(p.foreL);
  f['titanPistonR'] = 26 - 8 * math.sin(p.foreR);
  f['titanHammerL'] = hammer;
  f['titanHammerR'] = hammer;
  f['titanExternalFistL'] = action == 'quick' && t >= .26 && t < 1 ? 1 : 0;
  f['titanExternalFistR'] =
      ((action == 'attack' && t >= .22) ||
              (action == 'quick' && t >= .26) ||
              (skill && t >= titanSkillRelease)) &&
          t < 1
      ? 1
      : 0;
  if (action == 'quick') {
    f['titanHammerL'] = 10 * titanPunchReach(action, t, true);
    f['titanHammerR'] = 10 * titanPunchReach(action, t, false);
  }
  f['bodyscaleY'] = 1 - .02 * unit(math.max(0, p.y) / 24);
  f['bodyscaleX'] = 1 + .012 * stance;
  for (final side in [-1, 1]) {
    final label = side < 0 ? 'L' : 'R';
    final gait = action == 'move'
        ? math.sin(clock * 8 + (side < 0 ? 0 : math.pi))
        : action == 'dance'
        ? math.sin(t * math.pi * 8 + (side < 0 ? 0 : math.pi)) * .6
        : 0.0;
    f['titanLegX$label'] = side * (48 + stance * 11) + gait * 11;
    f['titanLegY$label'] = 40 - math.max(0, p.y) - tuck - math.max(0, gait) * 9;
    f[side < 0 ? 'joint8' : 'joint9'] = gait * .12;
    f[side < 0 ? 'joint14' : 'joint15'] = -gait * .1;
  }
  final social = {
    'joy',
    'dance',
    'wave',
    'victory',
    'playful',
    'feed',
  }.contains(action);
  p.smile = social ? 1 : 1 - .8 * math.max(charge, discharge);
  p.focus = math.max(charge, discharge);
  p.sad = 1 - power;
  p.eyeY = power * (social ? .72 : 1);
  p.eyeX = 1;
  p.brow = action == 'anger' ? .32 : p.focus * .16;
  if (action == 'surprise') {
    p.eyeY = 1 + .45 * pulse(t, .05, .8);
    p.eyeX = 1 + .18 * pulse(t, .05, .8);
    p.smile = 0;
  }
  if (action == 'defeat') {
    p.smile = 0;
    p.focus = 0;
    p.eyeY = .12 + .88 * power;
    p.brow = -.26 * (1 - power);
  }
  if (hit > 0) {
    p.x -= 8 * hit;
    p.body -= .12 * hit;
    p.head += .12 * hit;
  }
  return VoltFrame(
    action: action,
    t: t,
    charge: charge,
    discharge: discharge,
    shield: shield,
    shieldHit: hit,
    power: power,
    coilGlow: power,
    coreGlow: f['titanPress']!,
    trail: {'quick', 'dodge', 'move'}.contains(action)
        ? _hold(t, .1, .27, .6, .94)
        : 0,
    shockwave: heavy
        ? _ramp(t, titanQuakeRelease, titanQuakeRelease + .035) *
              (1 - _ramp(t, .94, 1))
        : 0,
    camera: heavy
        ? 1.8 * _hold(t, .62, .65, .8, 1)
        : skill
        ? .45 * titanPunchImpact(action, t, false)
        : hit * .4,
    flash: heavy ? .8 * pulse(t, titanQuakeRelease, .76) : 0,
    smoke: action == 'defeat' ? _hold(t, .2, .4, .85, 1) : charge * .5,
    sparks: action == 'victory' ? pulse(t, .15, .92) : 0,
    energyField: heavy ? charge : 0,
  );
}

void blendTitanPose(GamePose pose, GamePose old, double weight) {
  final w = smooth(weight);
  pose.blendFrom(old, w);
  for (final key in pose.extra.keys.toList()) {
    if (key.startsWith('titanExternalFist')) continue;
    if (!key.startsWith('titan') &&
        !key.startsWith('joint') &&
        !key.startsWith('bodyscale'))
      continue;
    final previous = old.extra[key] ?? pose.extra[key]!;
    var delta = pose.extra[key]! - previous;
    if (key == 'joint7') delta = (delta + math.pi) % (math.pi * 2) - math.pi;
    pose.extra[key] = previous + delta * w;
  }
}

Offset _rotate(Offset p, double a) => Offset(
  p.dx * math.cos(a) - p.dy * math.sin(a),
  p.dx * math.sin(a) + p.dy * math.cos(a),
);
Offset titanFist(
  GamePose p,
  Offset origin,
  double scale,
  double facing,
  bool left,
) {
  final arm = left ? p.armL : p.armR, fore = left ? p.foreL : p.foreR;
  var point =
      Offset(left ? -99 : 99, -55) +
      _rotate(const Offset(0, 48), arm) +
      _rotate(
        Offset(0, 75 + (p.extra[left ? 'titanHammerL' : 'titanHammerR'] ?? 0)),
        arm + fore,
      );
  point = _rotate(point, p.rotation);
  return origin + Offset(point.dx * facing, point.dy) * scale;
}

Offset titanWrist(
  GamePose p,
  Offset origin,
  double scale,
  double facing,
  bool left,
) {
  final arm = left ? p.armL : p.armR;
  final point = _rotate(
    Offset(left ? -99 : 99, -55) + _rotate(const Offset(0, 48), arm),
    p.rotation,
  );
  return origin + Offset(point.dx * facing, point.dy) * scale;
}
