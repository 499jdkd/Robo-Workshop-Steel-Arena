import 'dart:async';
import 'package:audioplayers/audioplayers.dart';
import 'package:flet/flet.dart';

/// Short, predecoded original sounds. Errors never block or alter a battle.
class SceneAudio {
  static const cues = [
    'deploy',
    'aim',
    'plasma',
    'sniper',
    'electric',
    'rocket',
    'impact',
    'shield',
    'feed',
    'victory',
    'laser',
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
    'volt_pulse',
    'volt_charge',
    'volt_storm',
    'volt_shutdown',
  ];
  final players = <String, AudioPlayer>{};
  final pending = <String, Future<AudioPlayer?>>{};
  FletBackend? backend;
  int epoch = 0;
  bool enabled = true, muted = false, disposed = false, configured = false;
  void configure(FletBackend backend) {
    if (configured || disposed) return;
    configured = true;
    this.backend = backend;
  }

  Future<AudioPlayer?> obtain(String cue) => pending.putIfAbsent(cue, () async {
    if (disposed || backend == null || !cues.contains(cue)) return null;
    final asset = backend!.getAssetSource('audio/$cue.wav');
    final player = AudioPlayer();
    players[cue] = player;
    try {
      await player.setReleaseMode(ReleaseMode.stop);
      await player.setVolume(cue == 'impact' ? .36 : .28);
      if (disposed) return null;
      await player.setSource(
        asset.isFile ? DeviceFileSource(asset.path) : UrlSource(asset.path),
      );
      return disposed ? null : player;
    } catch (_) {
      return null;
    }
  });

  void unlock() {
    /* Browser gesture is delivered to the audio plugin. */
  }
  void play(String cue) {
    if (!enabled || muted || disposed || backend == null) return;
    final current = epoch;
    unawaited(() async {
      try {
        final player = await obtain(cue);
        if (player == null || disposed || muted || !enabled || current != epoch)
          return;
        await player.seek(Duration.zero);
        if (!disposed && !muted && enabled && current == epoch)
          await player.resume();
      } catch (_) {}
    }());
  }

  void pause() {
    epoch++;
    for (final p in players.values) {
      unawaited(p.pause().catchError((_) {}));
    }
  }

  void dispose() {
    disposed = true;
    for (final p in players.values) {
      unawaited(p.dispose());
    }
    players.clear();
  }
}
