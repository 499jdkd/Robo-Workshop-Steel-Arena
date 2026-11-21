import 'dart:async';
import 'package:audioplayers/audioplayers.dart';
import 'package:flet/flet.dart';
import 'music_director.dart';
import 'game_audio_context.dart';

class NativeMusicVoice implements MusicVoice {
  NativeMusicVoice(this.backend, {this.ownsFocus = false});
  final FletBackend backend;
  final bool ownsFocus;
  AudioPlayer? _instance;
  AudioPlayer get _player =>
      _instance ??= (AudioPlayer()..positionUpdater = null);
  StreamSubscription<void>? _completion;
  bool _closed = false;
  @override
  Future<void> load(
    String track, {
    required bool loop,
    required void Function() onComplete,
  }) async {
    if (_closed) return;
    await _completion?.cancel();
    _completion = null;
    await _player.setAudioContext(gameAudioContext(musicOwner: ownsFocus));
    if (_closed) return;
    await _player.setReleaseMode(loop ? ReleaseMode.loop : ReleaseMode.stop);
    if (_closed) return;
    final source = backend.getAssetSource('audio/$track.ogg');
    await _player.setSource(
      source.isFile ? DeviceFileSource(source.path) : UrlSource(source.path),
    );
    if (!_closed && !loop)
      _completion = _player.onPlayerComplete.listen((_) => onComplete());
  }

  @override
  Future<bool> start({
    required bool restart,
    required bool Function() canPlay,
  }) async {
    if (_closed || !canPlay()) return false;
    if (restart) await _player.seek(Duration.zero);
    if (_closed || !canPlay()) return false;
    await _player.resume();
    // Playback was issued even if the app paused while resume was awaiting
    // the platform. Remember that position; the next reconciliation pauses it.
    return !_closed;
  }

  @override
  Future<void> volume(double gain) async {
    if (!_closed && _instance != null)
      await _player.setVolume(gain.clamp(0, 1));
  }

  @override
  Future<void> pause() async {
    if (!_closed && _instance != null) await _player.pause();
  }

  @override
  Future<void> dispose() async {
    if (_closed) return;
    _closed = true;
    await _completion?.cancel();
    await _instance?.dispose();
  }
}
