import 'dart:async';
import 'package:flet/flet.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flet_rive/src/robot/music_director.dart';
import 'package:flet_rive/src/robot/scene_audio.dart';
import 'package:flet_rive/src/robot/game_audio_context.dart';
import 'package:audioplayers/audioplayers.dart';
import 'robot_audio_test.dart' show FakeVoice;

class MusicFake implements MusicVoice {
  final tracks = <String>[];
  final restarts = <bool>[], gains = <double>[];
  void Function()? complete;
  Completer<void>? loading;
  Completer<void>? resuming;
  int pauses = 0, closes = 0;
  bool reject = false;
  @override
  Future<void> load(
    String track, {
    required bool loop,
    required void Function() onComplete,
  }) async {
    tracks.add(track);
    complete = onComplete;
    await loading?.future;
  }

  @override
  Future<bool> start({
    required bool restart,
    required bool Function() canPlay,
  }) async {
    if (!canPlay() || reject) return false;
    restarts.add(restart);
    await resuming?.future;
    return true;
  }

  @override
  Future<void> volume(double gain) async => gains.add(gain);
  @override
  Future<void> pause() async {
    pauses++;
  }

  @override
  Future<void> dispose() async {
    closes++;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late MusicFake bg, win;
  late MusicDirector music;
  setUp(() {
    bg = MusicFake();
    win = MusicFake();
    music = MusicDirector(background: bg, celebration: win, wait: (_) async {});
  });
  tearDown(() async {
    await music.close();
  });
  void state({
    String track = 'workshop',
    bool sound = true,
    bool pause = false,
    String victory = '',
  }) =>
      music.update(track: track, sound: sound, pause: pause, victory: victory);

  test('same state and route rebuilds keep exactly one loop', () async {
    state();
    await music.settle();
    for (var i = 0; i < 200; i++) state();
    await music.settle();
    expect(bg.tracks, ['music_workshop']);
    expect(bg.restarts, [true]);
    expect(bg.gains.last, closeTo(.115, 1e-9));
    expect(bg.gains.length, 7);
  });
  test('background change fades out before switching then fades in', () async {
    state();
    await music.settle();
    bg.gains.clear();
    state(track: 'arena');
    await music.settle();
    expect(bg.tracks, ['music_workshop', 'music_arena']);
    expect(
      bg.gains.take(6).toList(),
      orderedEquals(bg.gains.take(6).toList()..sort((a, b) => b.compareTo(a))),
    );
    expect(bg.gains[5], 0);
    expect(bg.gains.last, .115);
  });
  test(
    'victory completes naturally after animation/route/next battle changes',
    () async {
      state();
      await music.settle();
      state(victory: 'battle:1');
      await music.settle();
      expect(music.celebrating, isTrue);
      expect(win.restarts, [true]);
      final pauses = win.pauses;
      state(track: 'arena');
      state(track: 'workshop');
      await music.settle();
      expect(win.pauses, pauses);
      expect(win.restarts, [true]);
      win.complete!();
      await music.settle();
      expect(music.celebrating, isFalse);
      expect(bg.restarts, [true, false]);
      expect(bg.gains.last, .115);
    },
  );
  test(
    'rapid identical or overlapping victory requests cannot restart melody',
    () async {
      state(victory: 'preview:1');
      await music.settle();
      for (var i = 0; i < 100; i++) state(victory: 'preview:${i + 1}');
      await music.settle();
      expect(win.restarts, [true]);
      expect(win.tracks, ['music_victory']);
      win.complete!();
      await music.settle();
      state(victory: 'preview:100');
      await music.settle();
      expect(win.restarts, [true]);
      state(victory: 'preview:101');
      await music.settle();
      expect(win.restarts, [true, true]);
    },
  );
  test(
    'lifecycle pause resumes both loops and victory from position',
    () async {
      state();
      await music.settle();
      music.lifecycle(false);
      await music.settle();
      music.lifecycle(true);
      await music.settle();
      expect(bg.restarts, [true, false]);
      state(victory: 'battle:2');
      await music.settle();
      music.lifecycle(false);
      await music.settle();
      music.lifecycle(true);
      await music.settle();
      expect(win.restarts, [true, false]);
    },
  );
  test(
    'completion during pause restores desired track only after resume',
    () async {
      state(victory: 'battle:2');
      await music.settle();
      state(track: 'arena', pause: true);
      await music.settle();
      win.complete!();
      await music.settle();
      expect(bg.restarts, isEmpty);
      state(track: 'arena');
      await music.settle();
      expect(bg.tracks, ['music_arena']);
    },
  );
  test(
    'muted initial load is lazy, preference resumes without resetting position',
    () async {
      state(sound: false);
      await music.settle();
      expect(bg.tracks, isEmpty);
      state();
      await music.settle();
      music.preference(false);
      await music.settle();
      music.preference(true);
      await music.settle();
      expect(bg.restarts, [true, false]);
    },
  );
  test('pause during asynchronous load never starts stale audio', () async {
    bg.loading = Completer<void>();
    state();
    await Future<void>.delayed(Duration.zero);
    state(pause: true);
    bg.loading!.complete();
    await music.settle();
    expect(bg.restarts, isEmpty);
    state();
    await music.settle();
    expect(bg.restarts, [true]);
  });
  test('new desired background supersedes a slower load', () async {
    bg.loading = Completer<void>();
    state();
    await Future<void>.delayed(Duration.zero);
    state(track: 'arena');
    bg.loading!.complete();
    await music.settle();
    expect(bg.tracks, ['music_workshop', 'music_arena']);
    expect(bg.restarts, [true]);
  });
  test('stale completion from older victory cannot finish a new one', () async {
    state(victory: 'v1');
    await music.settle();
    final stale = win.complete!;
    stale();
    await music.settle();
    state(victory: 'v2');
    await music.settle();
    stale();
    await music.settle();
    expect(music.celebrating, isTrue);
  });
  test(
    'a pause while native resume is pending keeps the already issued position',
    () async {
      win.resuming = Completer<void>();
      state(victory: 'pending-resume');
      for (var i = 0; i < 5; i++) await Future<void>.delayed(Duration.zero);
      expect(win.restarts, [true]);
      music.lifecycle(false);
      win.resuming!.complete();
      await music.settle();
      music.lifecycle(true);
      await music.settle();
      expect(win.restarts, [true, false]);
    },
  );
  test(
    'autoplay denial retries only on a gesture and never restarts playing audio',
    () async {
      bg.reject = true;
      state();
      await music.settle();
      expect(bg.restarts, isEmpty);
      bg.reject = false;
      music.unlock();
      await music.settle();
      expect(bg.restarts, [true]);
      for (var i = 0; i < 100; i++) music.unlock();
      await music.settle();
      expect(bg.restarts, [true]);
    },
  );
  test(
    'scene SFX, old victory cue and scene disposal cannot stop application music',
    () async {
      final backend = FletBackend(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [],
      );
      bindMusic(backend, music);
      final effects = SceneAudio(voiceFactory: FakeVoice.new)
        ..configure(backend);
      state(victory: 'preview:1');
      await music.settle();
      final pauses = win.pauses;
      effects.play('victory', channel: 'player:action');
      for (final cue in ['volt_pulse', 'impact', 'shield', 'electric']) {
        effects.play(cue);
        await effects.settle();
      }
      effects.pause();
      effects.dispose();
      await music.settle();
      expect(win.pauses, pauses);
      expect(win.restarts, [true]);
      expect(music.celebrating, isTrue);
      bindMusic(backend, null);
      backend.dispose();
    },
  );
  test('closing while a load is pending prevents late playback', () async {
    win.loading = Completer<void>();
    state(victory: 'v1');
    await Future<void>.delayed(Duration.zero);
    await music.close();
    win.loading!.complete();
    await music.settle();
    expect(win.restarts, isEmpty);
    expect(bg.closes, 1);
    expect(win.closes, 1);
  });
  test('persisted mute can be toggled on a fresh robot scene', () async {
    final backend = FletBackend(
      pageUri: Uri.parse('http://localhost'),
      assetsDir: '',
      multiView: false,
      extensions: [],
    );
    bindMusic(backend, music);
    state(sound: false);
    await music.settle();
    final effects = SceneAudio(voiceFactory: FakeVoice.new)..configure(backend);
    expect(effects.muted, isTrue);
    effects.muted = false;
    await music.settle();
    expect(music.enabled, isTrue);
    expect(bg.restarts, [true]);
    effects.dispose();
    bindMusic(backend, null);
    backend.dispose();
  });
  test('effects and stinger mix without stealing Android music focus', () {
    expect(gameAudioContext().android.audioFocus, AndroidAudioFocus.none);
    expect(gameAudioContext().android.usageType, AndroidUsageType.game);
    expect(
      gameAudioContext(musicOwner: true).android.audioFocus,
      AndroidAudioFocus.gain,
    );
  });
  test(
    'explicit mute discards old victories while lifecycle pause preserves them',
    () async {
      state(victory: 'first');
      await music.settle();
      music.preference(false);
      await music.settle();
      state(sound: false, victory: 'muted');
      await music.settle();
      expect(music.celebrating, isFalse);
      state(victory: 'muted');
      await music.settle();
      expect(win.restarts, [true]);
      state(victory: 'new');
      await music.settle();
      expect(win.restarts, [true, true]);
    },
  );
}
