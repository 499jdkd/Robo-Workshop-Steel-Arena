/// Character audio for the existing non-Volt rigs. Only semantic events and
/// local, normalised animation time enter this director; it never changes game
/// state or starts a timer. Volt's battle actions keep their separate timeline;
/// his touch/dance reactions can use the same director without duplicating it.
class RobotAudioCue {
  const RobotAudioCue(
    this.at,
    this.name, {
    this.rate = 1,
    this.volume = 1,
    this.channel = 'action',
  });
  final double at, rate, volume;
  final String name, channel;
}

class RobotVoice {
  const RobotVoice(this.family, this.rate, this.power, this.movement);
  final String family, power, movement;
  final double rate;
}

const robotVoices = <String, RobotVoice>{
  'spark': RobotVoice('light', 1.12, 'plasma', 'robot_wheel'),
  'volt': RobotVoice('electric', 1.04, 'volt_pulse', 'robot_hover'),
  'flora': RobotVoice('bio', 1.04, 'repair', 'robot_servo'),
  'forge': RobotVoice('heavy', .86, 'impact', 'robot_wheel'),
  'nova': RobotVoice('spectral', 1.03, 'ion', 'robot_hover'),
  'glacier': RobotVoice('air', 1.12, 'cryo', 'robot_hover'),
  'aegis': RobotVoice('heavy', .79, 'shield', 'robot_wheel'),
  'solar': RobotVoice('bio', 1.10, 'flame', 'robot_hover'),
  'titan': RobotVoice('heavy', .72, 'impact', 'robot_step_heavy'),
  'arachna': RobotVoice('beast', 1.16, 'laser', 'robot_servo'),
  'phantom': RobotVoice('spectral', 1.18, 'ion', 'robot_hover'),
  'falcon': RobotVoice('air', 1.20, 'plasma', 'robot_hover'),
  'cyclops': RobotVoice('heavy', .96, 'sniper', 'robot_step_heavy'),
  'medic': RobotVoice('bio', 1.18, 'repair', 'robot_hover'),
  'atlas': RobotVoice('heavy', .76, 'impact', 'robot_step_heavy'),
  'cerberus': RobotVoice('beast', .84, 'machinegun', 'robot_step_heavy'),
  'cobra': RobotVoice('beast', 1.02, 'magnetic', 'robot_servo'),
  'phoenix': RobotVoice('air', 1.08, 'flame', 'robot_hover'),
  'driller': RobotVoice('heavy', .93, 'drill', 'robot_wheel'),
  'ninja': RobotVoice('light', 1.03, 'sword', 'robot_servo'),
  'specter': RobotVoice('spectral', 1.24, 'laser', 'robot_hover'),
  'magneto': RobotVoice('spectral', .88, 'magnetic', 'robot_hover'),
  'rocketeer': RobotVoice('heavy', 1.01, 'rocket', 'robot_wheel'),
  'octopus': RobotVoice('bio', .91, 'repair', 'robot_servo'),
  'scarab': RobotVoice('beast', .90, 'shield', 'robot_step_heavy'),
  'orbit': RobotVoice('spectral', 1.07, 'ion', 'robot_hover'),
  'guardian': RobotVoice('heavy', .84, 'shield', 'robot_step_heavy'),
  'goliath': RobotVoice('heavy', .70, 'rocket', 'robot_step_heavy'),
  'chronos': RobotVoice('spectral', .96, 'disc', 'robot_hover'),
  'omega': RobotVoice('beast', .96, 'blaster', 'robot_servo'),
  'storm': RobotVoice('air', .94, 'electric', 'robot_hover'),
  'chameleon': RobotVoice('beast', 1.12, 'laser', 'robot_servo'),
};

const robotAudioActions = <String>{
  'joy',
  'feed',
  'jump',
  'surprise',
  'fear',
  'anger',
  'inspect',
  'dance',
  'move',
  'attack',
  'quick',
  'pierce',
  'burst',
  'emp',
  'special',
  'ultimate',
  'guard',
  'dodge',
  'charge',
  'victory',
  'defeat',
};

String _weaponCue(String weapon, RobotVoice voice) => switch (weapon) {
  'fist' => 'electric',
  'plasma' ||
  'sniper' ||
  'rocket' ||
  'laser' ||
  'electric' ||
  'machinegun' ||
  'sword' ||
  'flame' ||
  'drone' ||
  'cryo' ||
  'ion' ||
  'blaster' ||
  'magnetic' ||
  'grenade' ||
  'emp' ||
  'drill' ||
  'disc' ||
  'repair' => weapon,
  _ => voice.power,
};

/// The generic articulated rigs release a shot at t=.28. The parent maps its
/// approach/flight/impact phases to this same timeline, including previews.
List<RobotAudioCue> robotAudioTimeline(
  String robot,
  String action, {
  String weapon = '',
}) {
  final voice = robotVoices[robot];
  if (voice == null) return const [];
  RobotAudioCue cue(
    double at,
    String name, {
    double rate = 1,
    double volume = 1,
    String channel = 'action',
  }) => RobotAudioCue(
    at,
    name,
    rate: (voice.rate * rate).clamp(.65, 1.35),
    volume: volume,
    channel: channel,
  );
  final reply = 'robot_reply_${voice.family}';
  switch (action) {
    case 'joy':
    case 'feed':
      return [cue(.035, reply, volume: .85, channel: 'reaction')];
    case 'jump':
      return [
        cue(.08, 'robot_servo', volume: .55),
        cue(.29, reply, rate: 1.08, volume: .7, channel: 'reaction'),
      ];
    case 'surprise':
    case 'fear':
      return [cue(.035, 'robot_surprise', volume: .75, channel: 'reaction')];
    case 'anger':
      return [
        cue(.045, 'robot_grump', rate: .9, volume: .8, channel: 'reaction'),
      ];
    case 'inspect':
      return [
        cue(.10, 'robot_servo', volume: .48),
        cue(.48, reply, volume: .45, channel: 'reaction'),
      ];
    case 'dance':
      final bass = voice.family == 'heavy'
          ? 'robot_step_heavy'
          : 'robot_dance_bass';
      final bright = {'bio', 'spectral', 'air'}.contains(voice.family)
          ? 'robot_dance_chime'
          : 'robot_dance_tick';
      return [
        cue(.10, bass, volume: .75, channel: 'dance'),
        cue(.30, bright, rate: 1.1, volume: .58, channel: 'dance'),
        cue(.50, bass, volume: .65, channel: 'dance'),
        cue(.70, 'robot_dance_tick', volume: .55, channel: 'dance'),
        cue(.90, bright, rate: 1.2, volume: .65, channel: 'dance'),
      ];
    case 'move':
      return [
        cue(.08, voice.movement, volume: .45, channel: 'movement'),
        if (voice.movement == 'robot_step_heavy') ...[
          cue(.39, voice.movement, volume: .40, channel: 'movement'),
          cue(.70, voice.movement, volume: .38, channel: 'movement'),
        ],
      ];
    case 'attack':
    case 'pierce':
    case 'burst':
      return [
        cue(.035, weapon == 'sniper' ? 'aim' : 'robot_servo', volume: .55),
        cue(.285, _weaponCue(weapon, voice)),
      ];
    case 'quick':
      return [
        cue(.045, 'robot_servo', rate: 1.15, volume: .45),
        cue(.285, _weaponCue(weapon, voice), rate: 1.08, volume: .9),
      ];
    case 'emp':
      return [cue(.04, 'robot_charge', volume: .6), cue(.285, 'emp')];
    case 'special':
      return [cue(.025, 'robot_charge', volume: .65), cue(.30, voice.power)];
    case 'ultimate':
      return [
        cue(.025, 'robot_charge', rate: .85, volume: .8),
        cue(.12, reply, rate: .9, volume: .45),
        cue(.30, voice.power, rate: .92, volume: 1.1),
      ];
    case 'guard':
      return [cue(.12, 'shield', volume: .85)];
    case 'dodge':
      return [cue(.14, voice.movement, rate: 1.2, volume: .65)];
    case 'charge':
      return [
        cue(.06, 'robot_charge', volume: .75),
        cue(.57, 'repair', volume: .5),
      ];
    case 'victory':
      return [
        cue(.05, reply, rate: 1.12, volume: .75, channel: 'reaction'),
        cue(.24, 'victory', volume: .65),
      ];
    case 'defeat':
      return [
        cue(
          .06,
          'robot_powerdown',
          rate: .92,
          volume: .85,
          channel: 'reaction',
        ),
      ];
    default:
      return const [];
  }
}

class _AudioTrack {
  _AudioTrack(this.identity, this.t, this.timeline);
  String identity;
  double t;
  List<RobotAudioCue> timeline;
}

class RobotSoundDirector {
  RobotSoundDirector(this.emit);
  final void Function(RobotAudioCue cue) emit;
  final _tracks = <String, _AudioTrack>{};

  /// Tokens identify one logical action, not Flet's per-phase update. Disabled
  /// samples advance history too, so enabling sound cannot replay a backlog.
  void sample({
    required String slot,
    required String robot,
    required String action,
    required double t,
    required Object token,
    String weapon = '',
    bool enabled = true,
  }) {
    if (!t.isFinite) return;
    final now = t.clamp(0.0, 1.0);
    final identity = '$robot|$action|$token|$weapon';
    var track = _tracks[slot];
    final fresh =
        track == null || track.identity != identity || now + .05 < track.t;
    // Minor phase jitter must not move the cursor backwards across a cue.
    if (!fresh && now < track.t) return;
    final before = fresh ? -.0001 : track.t;
    if (track == null) {
      // There are only player/enemy tracks in a scene. Bound accidental caller
      // growth without retaining identities across a long collection session.
      if (_tracks.length >= 4) _tracks.remove(_tracks.keys.first);
      track = _tracks[slot] = _AudioTrack(
        identity,
        now,
        robotAudioTimeline(robot, action, weapon: weapon),
      );
    } else {
      if (track.identity != identity) {
        track.timeline = robotAudioTimeline(robot, action, weapon: weapon);
      }
      track.identity = identity;
      track.t = now;
    }
    if (!enabled) return;
    // Timelines belong to logical actions. The 60 Hz sample path neither
    // recreates cue lists nor allocates an intermediate collection.
    RobotAudioCue? previous, latest;
    for (final cue in track.timeline) {
      if (before < cue.at &&
          now >= cue.at &&
          (now - before <= .20 || now - cue.at <= .12)) {
        previous = latest;
        latest = cue;
      }
    }
    // One slow frame must not dump a complete dance or all preparatory sounds.
    void send(RobotAudioCue cue) {
      emit(
        RobotAudioCue(
          cue.at,
          cue.name,
          rate: cue.rate,
          volume: cue.volume,
          channel: '$slot:${cue.channel}',
        ),
      );
    }

    if (previous != null) send(previous);
    if (latest != null) send(latest);
  }

  void reset({String? slot}) {
    if (slot == null)
      _tracks.clear();
    else
      _tracks.remove(slot);
  }
}
