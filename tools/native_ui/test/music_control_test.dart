import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flet_rive/src/game_music.dart';
import 'package:flet_rive/src/robot/music_director.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/scene_audio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'music_director_test.dart' show MusicFake;
import 'robot_audio_test.dart' show FakeVoice;

void main() {
  testWidgets(
    'a gesture on another UI control unlocks denied background playback',
    (tester) async {
      final backend = FletBackend(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [],
      );
      final bg = MusicFake()..reject = true, win = MusicFake();
      final music = MusicDirector(
        background: bg,
        celebration: win,
        wait: (_) async {},
      );
      final control = Control.fromMap({
        '_c': 'GameMusic',
        '_i': 501,
        'payload': jsonEncode({'sound': true}),
      }, backend);
      await tester.pumpWidget(
        MaterialApp(
          home: Column(
            children: [
              GameMusicControl(control: control, director: music),
              TextButton(onPressed: () {}, child: const Text('Shop')),
            ],
          ),
        ),
      );
      await music.settle();
      expect(bg.restarts, isEmpty);
      bg.reject = false;
      await tester.tap(find.text('Shop'));
      await music.settle();
      expect(bg.restarts, [true]);
      await tester.pumpWidget(const SizedBox.shrink());
      await music.close();
      backend.dispose();
    },
  );
  test(
    'visual local/PvP victory phase owns the jingle, not early combat resolution',
    () async {
      final backend = FletBackend(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [],
      );
      final bg = MusicFake(), win = MusicFake();
      final music = MusicDirector(
        background: bg,
        celebration: win,
        wait: (_) async {},
      );
      bindMusic(backend, music);
      music.update(track: 'arena', sound: true, pause: false);
      await music.settle();
      GameSceneClock scene() => GameSceneClock(
        sceneAudio: SceneAudio(voiceFactory: FakeVoice.new)..configure(backend),
      )..viewport = const Size(844, 390);
      final first = scene();
      final data = <String, dynamic>{
        'robot': 'volt',
        'enemy': 'spark',
        'arena': true,
        'sound': true,
        'phase': 'flight',
        'event': 'online-match:4:2:flight',
        'action': 'attack',
        'combatAction': 'attack',
        'result': 'win',
      };
      final hidden = scene();
      hidden.update({...data, 'phase': 'victory', 'sampleOnly': true});
      hidden.advance(0);
      await music.settle();
      expect(win.restarts, isEmpty);
      hidden.dispose();
      first.update(data);
      first.advance(.1);
      await music.settle();
      expect(win.restarts, isEmpty);
      first.update({
        ...data,
        'phase': 'impact',
        'event': 'online-match:4:2:impact',
      });
      first.advance(.1);
      await music.settle();
      expect(win.restarts, isEmpty);
      first.update({
        ...data,
        'phase': 'victory',
        'event': 'online-match:4:2:victory',
      });
      first.advance(0);
      await music.settle();
      expect(win.restarts, [true]);
      first.dispose();
      final remounted = scene();
      remounted.update({
        ...data,
        'phase': 'idle',
        'event': 'online-match:4:2:idle',
      });
      remounted.advance(.2);
      await music.settle();
      expect(win.restarts, [true]);
      win.complete!();
      await music.settle();
      remounted.update({
        ...data,
        'phase': 'victory',
        'event': 'lost-match:1:0:victory',
        'result': 'loss',
      });
      remounted.advance(.2);
      await music.settle();
      expect(win.restarts, [true]);
      remounted.dispose();
      bindMusic(backend, null);
      await music.close();
      backend.dispose();
    },
  );
  testWidgets(
    'application music survives replacing the complete route subtree',
    (tester) async {
      final backend = FletBackend(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [],
      );
      final bg = MusicFake(), win = MusicFake();
      final director = MusicDirector(
        background: bg,
        celebration: win,
        wait: (_) async {},
      );
      final control = Control.fromMap({
        '_c': 'GameMusic',
        '_i': 401,
        'payload': jsonEncode({'track': 'workshop', 'sound': true}),
      }, backend);
      Widget host(String route) => MaterialApp(
        home: Column(
          children: [
            GameMusicControl(
              key: const ValueKey('application-music'),
              control: control,
              director: director,
            ),
            Expanded(child: Container(key: ValueKey(route))),
          ],
        ),
      );
      await tester.pumpWidget(host('workshop'));
      await director.settle();
      expect(musicFor(backend), same(director));
      control.properties['payload'] = jsonEncode({
        'track': 'workshop',
        'sound': true,
        'victory': 'preview:1',
      });
      await tester.pumpWidget(host('inspect'));
      await director.settle();
      final pauses = win.pauses;
      for (final route in ['collection', 'profile', 'factory', 'workshop']) {
        await tester.pumpWidget(host(route));
        await director.settle();
      }
      expect(win.restarts, [true]);
      expect(win.pauses, pauses);
      expect(bg.tracks, ['music_workshop']);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await director.settle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await director.settle();
      expect(win.restarts, [true, false]);
      win.complete!();
      await director.settle();
      expect(bg.restarts, [true, false]);
      await tester.pumpWidget(const SizedBox.shrink());
      await director.close();
      expect(musicFor(backend), isNull);
      expect(bg.closes, 1);
      expect(win.closes, 1);
      backend.dispose();
      expect(tester.takeException(), isNull);
    },
  );
}
