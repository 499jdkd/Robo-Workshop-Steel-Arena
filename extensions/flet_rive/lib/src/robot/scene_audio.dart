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
    'cryo','ion','blaster','magnetic','grenade','emp','drill','disc','repair',
  ];
  final players = <String, AudioPlayer>{};
  bool enabled = true, muted = false, disposed = false, configured = false;
  void configure(FletBackend backend) {
    if (configured || disposed) return;
    configured = true;
    for (final cue in cues) {
      final asset = backend.getAssetSource('audio/$cue.wav');
      final player = AudioPlayer();
      players[cue] = player;
      unawaited(() async {
        try {
          await player.setReleaseMode(ReleaseMode.stop);
          await player.setVolume(cue == 'impact' ? .36 : .28);
          if (disposed) return;
          await player.setSource(
            asset.isFile ? DeviceFileSource(asset.path) : UrlSource(asset.path),
          );
        } catch (_) {
          /* Browser audio can wait for the first gesture. */
        }
      }());
    }
  }

  void unlock() {
    /* Browser gesture is delivered to the audio plugin. */
  }
  void play(String cue) {
    if (!enabled || muted || disposed) return;
    final player = players[cue];
    if (player == null) return;
    unawaited(() async {
      try {
        await player.seek(Duration.zero);
        if (!disposed && !muted && enabled) await player.resume();
      } catch (_) {}
    }());
  }

  void pause() {
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
