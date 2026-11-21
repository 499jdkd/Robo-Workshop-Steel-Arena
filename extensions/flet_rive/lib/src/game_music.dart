import 'dart:async';
import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter/gestures.dart';
import 'robot/music_director.dart';
import 'robot/music_voice.dart';

class GameMusicControl extends StatefulWidget {
  const GameMusicControl({super.key, required this.control, this.director});
  final Control control;
  final MusicDirector? director;
  @override
  State<GameMusicControl> createState() => _GameMusicControlState();
}

class _GameMusicControlState extends State<GameMusicControl>
    with WidgetsBindingObserver {
  late final MusicDirector music;
  @override
  void initState() {
    super.initState();
    final backend = widget.control.backend;
    music =
        widget.director ??
        MusicDirector(
          background: NativeMusicVoice(backend, ownsFocus: true),
          celebration: NativeMusicVoice(backend),
          onPreference: (enabled) {
            widget.control.triggerEvent('sound_change', {'enabled': enabled});
          },
        );
    bindMusic(backend, music);
    WidgetsBinding.instance.addObserver(this);
    GestureBinding.instance.pointerRouter.addGlobalRoute(unlock);
    final state = WidgetsBinding.instance.lifecycleState;
    music.lifecycle(state == null || state == AppLifecycleState.resumed);
  }

  void unlock(PointerEvent event) {
    if (event is PointerDownEvent) music.unlock();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) =>
      music.lifecycle(state == AppLifecycleState.resumed);
  @override
  Widget build(BuildContext context) {
    final data =
        jsonDecode(widget.control.getString('payload', '{}')!)
            as Map<String, dynamic>;
    music.update(
      track: data['track'] as String? ?? 'workshop',
      sound: data['sound'] != false,
      pause: data['paused'] == true,
      victory: data['victory'] as String? ?? '',
    );
    return const SizedBox.shrink();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    GestureBinding.instance.pointerRouter.removeGlobalRoute(unlock);
    if (identical(musicFor(widget.control.backend), music))
      bindMusic(widget.control.backend, null);
    unawaited(music.close().catchError((_) {}));
    super.dispose();
  }
}
