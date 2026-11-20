import 'dart:async';
import 'dart:io';

import 'package:flet/flet.dart';
import 'package:flet_rive/src/robot/robot_audio.dart';
import 'package:flet_rive/src/robot/scene_audio.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeVoice implements SceneVoice {
  String cue = '';
  Completer<void>? preparation, starting;
  bool fail = false, disposed = false;
  int plays = 0, pauses = 0;
  double? rate, volume;

  @override
  Future<void> prepare(FletBackend? backend, String value) async {
    cue = value;
    await preparation?.future;
    if (fail) throw StateError('speaker unavailable');
  }

  @override
  Future<bool> start({
    required double rate,
    required double volume,
    required bool Function() canPlay,
  }) async {
    await starting?.future;
    if (disposed || !canPlay()) return false;
    this.rate = rate;
    this.volume = volume;
    plays++;
    return true;
  }

  @override
  Future<void> pause() async => pauses++;

  @override
  Future<void> dispose() async => disposed = true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('every robot has complete, bounded timelines and packaged WAV cues', () {
    expect(robotVoices, hasLength(32));
    expect(
      robotVoices.values.map((voice) => voice.family).toSet(),
      hasLength(7),
    );
    for (final robot in robotVoices.keys) {
      for (final action in robotAudioActions) {
        final cues = robotAudioTimeline(robot, action);
        expect(cues, isNotEmpty, reason: '$robot $action');
        var last = -1.0;
        for (final cue in cues) {
          expect(cue.at, inInclusiveRange(0, 1));
          expect(cue.at, greaterThanOrEqualTo(last));
          expect(cue.rate, inInclusiveRange(.65, 1.35));
          expect(cue.volume, inInclusiveRange(0, 1.2));
          expect(SceneAudio.cueSeconds.containsKey(cue.name), isTrue);
          final file = File('../../src/assets/audio/${cue.name}.wav');
          expect(file.existsSync(), isTrue, reason: cue.name);
          final bytes = file.readAsBytesSync();
          expect(String.fromCharCodes(bytes.take(4)), 'RIFF');
          expect(String.fromCharCodes(bytes.skip(8).take(4)), 'WAVE');
          last = cue.at;
        }
      }
    }
    expect(robotAudioTimeline('unknown', 'joy'), isEmpty);
    expect(robotAudioTimeline('spark', 'idle'), isEmpty);
  });

  test('family voices, movement and equipped weapon affect the heard cue', () {
    final heavy = robotAudioTimeline('titan', 'joy').single;
    final light = robotAudioTimeline('spark', 'joy').single;
    expect(heavy.name, 'robot_reply_heavy');
    expect(light.name, 'robot_reply_light');
    expect(heavy.rate, lessThan(light.rate));
    expect(robotAudioTimeline('titan', 'move'), hasLength(3));
    expect(robotAudioTimeline('falcon', 'move').single.name, 'robot_hover');
    expect(robotAudioTimeline('ninja', 'attack').last.name, 'sword');
    expect(
      robotAudioTimeline('ninja', 'attack', weapon: 'rocket').last.name,
      'rocket',
    );
    expect(robotAudioTimeline('titan', 'dance').first.name, 'robot_step_heavy');
    expect(robotAudioTimeline('phantom', 'dance')[1].name, 'robot_dance_chime');
  });

  test('stable action token never repeats on frame or Flet phase updates', () {
    final heard = <RobotAudioCue>[];
    final director = RobotSoundDirector(heard.add);
    for (var frame = 0; frame <= 120; frame++) {
      director.sample(
        slot: 'player',
        robot: 'spark',
        action: 'attack',
        t: frame / 120,
        token: 'battle-1:action-2',
      );
    }
    expect(heard.map((cue) => cue.name), ['robot_servo', 'plasma']);
    expect(heard.every((cue) => cue.channel.startsWith('player:')), isTrue);
    director.sample(
      slot: 'player',
      robot: 'spark',
      action: 'attack',
      t: 1,
      token: 'battle-1:action-2',
    );
    expect(heard, hasLength(2));
    director.sample(
      slot: 'player',
      robot: 'spark',
      action: 'attack',
      t: .04,
      token: 'battle-1:action-3',
    );
    expect(heard, hasLength(3));
  });

  test('player and opponent use independent reaction channels', () {
    final heard = <RobotAudioCue>[];
    final director = RobotSoundDirector(heard.add);
    director.sample(
      slot: 'player',
      robot: 'spark',
      action: 'victory',
      t: .06,
      token: 1,
    );
    director.sample(
      slot: 'enemy',
      robot: 'titan',
      action: 'defeat',
      t: .07,
      token: 1,
    );
    expect(heard.map((cue) => cue.channel), [
      'player:reaction',
      'enemy:reaction',
    ]);
  });

  test('small phase jitter cannot cross a cue twice', () {
    final heard = <RobotAudioCue>[];
    final director = RobotSoundDirector(heard.add);
    for (final t in [.09, .11, .09, .11, .12]) {
      director.sample(
        slot: 'player',
        robot: 'spark',
        action: 'dance',
        t: t,
        token: 1,
      );
    }
    expect(heard, hasLength(1));
  });

  test('muted frames advance history and cannot replay after enabling', () {
    final heard = <RobotAudioCue>[];
    final director = RobotSoundDirector(heard.add);
    for (var frame = 0; frame <= 60; frame++) {
      director.sample(
        slot: 'player',
        robot: 'flora',
        action: 'dance',
        t: frame / 60,
        token: 2,
        enabled: frame > 45,
      );
    }
    expect(heard, hasLength(1));
    expect(heard.single.at, .9);
    director.reset();
    director.sample(
      slot: 'player',
      robot: 'flora',
      action: 'joy',
      t: .04,
      token: 2,
    );
    expect(heard, hasLength(2));
  });

  test(
    'a stalled frame drops old cues instead of bursting the whole dance',
    () {
      final heard = <RobotAudioCue>[];
      final director = RobotSoundDirector(heard.add);
      director.sample(
        slot: 'player',
        robot: 'spark',
        action: 'dance',
        t: 0,
        token: 1,
      );
      director.sample(
        slot: 'player',
        robot: 'spark',
        action: 'dance',
        t: .93,
        token: 1,
      );
      expect(heard, hasLength(1));
      expect(heard.single.at, .9);
      director.sample(
        slot: 'player',
        robot: 'spark',
        action: 'joy',
        t: double.nan,
        token: 2,
      );
      expect(heard, hasLength(1));
    },
  );

  test(
    'SceneAudio bounds live voices and clamps native gain and rate',
    () async {
      var now = 0.0;
      final voices = <FakeVoice>[];
      final audio = SceneAudio(
        voiceFactory: () {
          final v = FakeVoice();
          voices.add(v);
          return v;
        },
        now: () => now,
      );
      audio.play('robot_servo', rate: 99, volume: 99, channel: 'player:action');
      await audio.settle();
      expect(voices.single.rate, 1.35);
      expect(voices.single.volume, closeTo(.336, .0001));
      for (final cue in ['shield', 'impact', 'electric']) {
        now += .1;
        audio.play(cue);
        await audio.settle();
      }
      expect(audio.activeVoiceCount, 3);
      expect(voices.first.pauses, greaterThan(0));
      audio.dispose();
      expect(voices.every((voice) => voice.disposed), isTrue);
    },
  );

  test(
    'same channel replaces interrupted gestures without stopping opponent',
    () async {
      final voices = <FakeVoice>[];
      final audio = SceneAudio(
        voiceFactory: () {
          final v = FakeVoice();
          voices.add(v);
          return v;
        },
      );
      audio.play('robot_reply_heavy', channel: 'enemy:reaction');
      audio.play('robot_reply_light', channel: 'player:reaction');
      await audio.settle();
      audio.play('robot_grump', channel: 'player:reaction');
      await audio.settle();
      expect(voices[0].pauses, 0);
      expect(voices[1].pauses, 1);
      expect(audio.activeVoiceCount, 2);
      audio.dispose();
    },
  );

  test('older asynchronous load cannot overtake the newest gesture', () async {
    final slow = FakeVoice()..preparation = Completer<void>();
    final latest = FakeVoice();
    var creations = 0;
    final audio = SceneAudio(
      voiceFactory: () => creations++ == 0 ? slow : latest,
    );
    audio.play('robot_reply_light', channel: 'player:reaction');
    audio.play('robot_grump', channel: 'player:reaction');
    await Future<void>.delayed(Duration.zero);
    slow.preparation!.complete();
    await audio.settle();
    expect(slow.plays, 0);
    expect(latest.plays, 1);
    audio.dispose();
  });

  test('late loads are discarded and same-cue spam is coalesced', () async {
    var now = 0.0;
    final voice = FakeVoice()..preparation = Completer<void>();
    var creations = 0;
    final audio = SceneAudio(
      voiceFactory: () {
        creations++;
        return voice;
      },
      now: () => now,
    );
    audio.play('electric');
    audio.play('electric');
    now = .5;
    voice.preparation!.complete();
    await audio.settle();
    expect(creations, 1);
    expect(voice.plays, 0);
    now = .6;
    audio.play('electric');
    await audio.settle();
    expect(voice.plays, 1);
    audio.dispose();
  });

  for (final cancellation in ['mute', 'disable', 'pause', 'dispose']) {
    test(
      '$cancellation cancels pending preparation and in-flight start',
      () async {
        for (final preparing in [true, false]) {
          final gate = Completer<void>();
          final voice = FakeVoice();
          if (preparing) {
            voice.preparation = gate;
          } else {
            voice.starting = gate;
          }
          final audio = SceneAudio(voiceFactory: () => voice);
          audio.play('robot_reply_light');
          await Future<void>.delayed(Duration.zero);
          switch (cancellation) {
            case 'mute':
              audio.muted = true;
            case 'disable':
              audio.enabled = false;
            case 'pause':
              audio.pause();
            case 'dispose':
              audio.dispose();
          }
          gate.complete();
          await audio.settle();
          expect(voice.plays, 0, reason: '$cancellation preparing=$preparing');
          expect(audio.activeVoiceCount, 0);
          audio.dispose();
        }
      },
    );
  }

  test(
    'LRU evicts inactive players and loading voices remain bounded',
    () async {
      final voices = <FakeVoice>[];
      final audio = SceneAudio(
        maximumCachedVoices: 3,
        maximumVoices: 2,
        voiceFactory: () {
          final voice = FakeVoice();
          voices.add(voice);
          return voice;
        },
      );
      for (final cue in ['electric', 'shield', 'impact']) {
        await audio.obtain(cue);
      }
      await audio.obtain('robot_servo');
      expect(voices.first.disposed, isTrue);
      expect(audio.players, hasLength(3));
      audio.dispose();

      final gate = Completer<void>();
      var count = 0;
      final loading = SceneAudio(
        maximumCachedVoices: 3,
        maximumVoices: 2,
        voiceFactory: () {
          count++;
          return FakeVoice()..preparation = gate;
        },
      );
      loading.play('electric');
      loading.play('shield');
      loading.play('impact');
      loading.play('robot_servo');
      expect(count, 3);
      expect(loading.players, hasLength(3));
      gate.complete();
      await loading.settle();
      expect(loading.activeVoiceCount, 2);
      loading.dispose();
    },
  );

  test('speaker preparation failure leaves no poisoned cache entry', () async {
    final broken = FakeVoice()..fail = true;
    final audio = SceneAudio(voiceFactory: () => broken);
    audio.play('electric');
    await audio.settle();
    expect(audio.players, isEmpty);
    expect(broken.disposed, isTrue);
    expect(audio.activeVoiceCount, 0);
    audio.dispose();
  });
}
