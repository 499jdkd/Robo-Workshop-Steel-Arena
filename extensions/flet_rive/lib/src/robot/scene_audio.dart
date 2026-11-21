import 'dart:async';
import 'dart:collection';
import 'package:audioplayers/audioplayers.dart';
import 'package:flet/flet.dart';
import 'music_director.dart';
import 'game_audio_context.dart';

/// Injectable player boundary for deterministic asynchronous race tests.
abstract class SceneVoice {
  Future<void> prepare(FletBackend? backend, String cue);
  Future<bool> start({
    required double rate,
    required double volume,
    required bool Function() canPlay,
  });
  Future<void> pause();
  Future<void> dispose();
}

class _NativeSceneVoice implements SceneVoice {
  final player = AudioPlayer()..positionUpdater = null;
  String cue = '';
  bool disposed = false;
  @override
  Future<void> prepare(FletBackend? backend, String cue) async {
    if (backend == null || disposed) return;
    this.cue = cue;
    final asset = backend.getAssetSource('audio/$cue.wav');
    await player.setAudioContext(gameAudioContext());
    if (disposed) return;
    await player.setReleaseMode(ReleaseMode.stop);
    if (disposed) return;
    await player.setSource(
      asset.isFile ? DeviceFileSource(asset.path) : UrlSource(asset.path),
    );
  }

  @override
  Future<bool> start({
    required double rate,
    required double volume,
    required bool Function() canPlay,
  }) async {
    if (disposed || !canPlay()) return false;
    await player.setPlaybackRate(rate);
    if (disposed || !canPlay()) return false;
    await player.setVolume(volume);
    if (disposed || !canPlay()) return false;
    await player.seek(
      Duration(
        microseconds: ((SceneAudio.cueStartSeconds[cue] ?? 0) * 1000000)
            .round(),
      ),
    );
    if (disposed || !canPlay()) return false;
    await player.resume();
    return !disposed && canPlay();
  }

  @override
  Future<void> pause() async {
    if (!disposed) await player.pause();
  }

  @override
  Future<void> dispose() async {
    if (disposed) return;
    disposed = true;
    await player.dispose();
  }
}

class _ActiveVoice {
  _ActiveVoice(this.voice, this.channel, this.until);
  final SceneVoice voice;
  final String channel;
  final double until;
}

/// Bounded lazy cache and at most three live voices. Late loads and interrupted
/// reactions are discarded instead of being queued behind a burst of touches.
class SceneAudio {
  SceneAudio({
    SceneVoice Function()? voiceFactory,
    double Function()? now,
    this.maximumVoices = 3,
    this.maximumCachedVoices = 12,
    this.maximumDelay = .35,
  }) : assert(maximumVoices > 0 && maximumCachedVoices >= maximumVoices),
       _voiceFactory = voiceFactory ?? _NativeSceneVoice.new,
       _injected = voiceFactory != null {
    final watch = Stopwatch()..start();
    _now = now ?? () => watch.elapsedMicroseconds / 1000000;
  }

  static const cueSeconds = <String, double>{
    'deploy': .35,
    'aim': .48,
    'plasma': .5,
    'sniper': .42,
    'electric': .62,
    'rocket': .75,
    'impact': .52,
    'shield': .6,
    'feed': .55,
    'victory': 1.15,
    'laser': .55,
    'machinegun': .5,
    'sword': .5,
    'flame': .8,
    'drone': .65,
    'cryo': .62,
    'ion': .7,
    'blaster': .4,
    'magnetic': .65,
    'grenade': .8,
    'emp': .7,
    'drill': .75,
    'disc': .6,
    'repair': .8,
    'volt_pulse': .43,
    'volt_charge': .56,
    'volt_storm': .9,
    'volt_shutdown': .9,
    'robot_reply_light': .22,
    'robot_reply_heavy': .28,
    'robot_reply_bio': .27,
    'robot_reply_air': .25,
    'robot_reply_spectral': .29,
    'robot_reply_beast': .26,
    'robot_reply_electric': .24,
    'robot_servo': .17,
    'robot_step_heavy': .19,
    'robot_wheel': .23,
    'robot_hover': .22,
    'robot_dance_tick': .10,
    'robot_dance_bass': .18,
    'robot_dance_chime': .23,
    'robot_surprise': .22,
    'robot_grump': .26,
    'robot_powerdown': .43,
    'robot_charge': .34,
  };
  static final cues = cueSeconds.keys.toList(growable: false);
  // The preserved storm WAV begins with 300ms of charging. Charging has its
  // own cues; start at its strike so arena speed cannot desynchronise the hit.
  static const cueStartSeconds = <String, double>{'volt_storm': .30};
  final SceneVoice Function() _voiceFactory;
  final bool _injected;
  late final double Function() _now;
  final int maximumVoices, maximumCachedVoices;
  final double maximumDelay;
  final players = LinkedHashMap<String, SceneVoice>();
  final pending = <String, Future<SceneVoice?>>{};
  final _active = LinkedHashMap<String, _ActiveVoice>();
  final _lastRequested = <String, double>{};
  final _requestGeneration = <String, int>{};
  final _channelGeneration = <String, int>{};
  Future<void> _serial = Future.value();
  FletBackend? backend;
  int epoch = 0;
  bool disposed = false, configured = false;
  bool _enabled = true, _muted = false;
  String _musicToken = '';
  int get activeVoiceCount => _active.length;
  bool get enabled => _enabled;
  set enabled(bool value) {
    if (_enabled == value) return;
    _enabled = value;
    if (!value) pause();
  }

  bool get muted =>
      _muted || (backend != null && musicFor(backend!)?.enabled == false);
  set muted(bool value) {
    if (_muted == value && muted == value) return;
    _muted = value;
    if (backend != null) musicFor(backend!)?.preference(!value);
    if (value) pause();
  }

  void configure(FletBackend backend) {
    if (configured || disposed) return;
    configured = true;
    this.backend = backend;
  }

  void _release(SceneVoice voice) {
    unawaited(voice.dispose().catchError((_) {}));
  }

  bool _makeCacheRoom() {
    while (players.length >= maximumCachedVoices) {
      final candidates = players.keys
          .where(
            (key) => !_active.containsKey(key) && !pending.containsKey(key),
          )
          .toList();
      if (candidates.isEmpty) return false;
      _release(players.remove(candidates.first)!);
    }
    return true;
  }

  Future<SceneVoice?> _prepare(String cue) async {
    SceneVoice? voice;
    try {
      final created = _voiceFactory();
      voice = created;
      players[cue] = created;
      await created.prepare(backend, cue);
      return disposed || !identical(players[cue], created) ? null : created;
    } catch (_) {
      if (voice != null) {
        if (identical(players[cue], voice)) players.remove(cue);
        _release(voice);
      }
      return null;
    }
  }

  Future<SceneVoice?> obtain(String cue) {
    if (disposed ||
        (!_injected && backend == null) ||
        !cueSeconds.containsKey(cue))
      return Future.value();
    final cached = players.remove(cue);
    if (cached != null) {
      players[cue] = cached;
      return pending[cue] ?? Future.value(cached);
    }
    if (pending.containsKey(cue)) return pending[cue]!;
    if (!_makeCacheRoom()) return Future.value();
    final loading = _prepare(cue);
    pending[cue] = loading;
    unawaited(
      loading.then((_) {
        if (identical(pending[cue], loading)) pending.remove(cue);
      }),
    );
    return loading;
  }

  void unlock() {
    if (backend != null) musicFor(backend!)?.unlock();
  }

  void celebrate(String token) {
    if (backend == null || token == _musicToken) return;
    final music = musicFor(backend!);
    if (music == null) return;
    _musicToken = token;
    music.celebrate(token);
  }

  void play(
    String cue, {
    double rate = 1,
    double volume = 1,
    String channel = '',
  }) {
    // The persistent application music controller owns the complete victory
    // phrase. Scene changes and the bounded SFX pool must not stop it.
    if (cue == 'victory' && backend != null && musicFor(backend!) != null)
      return;
    if (!enabled ||
        muted ||
        disposed ||
        (!_injected && backend == null) ||
        !cueSeconds.containsKey(cue) ||
        !rate.isFinite ||
        !volume.isFinite)
      return;
    final requested = _now();
    if (requested - (_lastRequested[cue] ?? -99) < .075) return;
    _lastRequested[cue] = requested;
    final currentEpoch = epoch;
    final generation = (_requestGeneration[cue] ?? 0) + 1;
    _requestGeneration[cue] = generation;
    final channelGeneration = channel.isEmpty
        ? 0
        : (_channelGeneration[channel] ?? 0) + 1;
    if (channel.isNotEmpty) _channelGeneration[channel] = channelGeneration;
    final speed = rate.clamp(.65, 1.35);
    final gain = ((cue == 'impact' ? .36 : .28) * volume.clamp(0.0, 1.2)).clamp(
      0.0,
      .42,
    );
    bool valid() =>
        !disposed &&
        enabled &&
        !muted &&
        epoch == currentEpoch &&
        _requestGeneration[cue] == generation &&
        (channel.isEmpty || _channelGeneration[channel] == channelGeneration) &&
        _now() - requested <= maximumDelay;
    unawaited(() async {
      try {
        final voice = await obtain(cue);
        if (voice == null || !valid()) return;
        _serial = _serial.catchError((_) {}).then((_) async {
          if (!valid() || !identical(players[cue], voice)) return;
          final now = _now();
          final stopping = _active.keys.where((key) {
            final active = _active[key]!;
            return active.until <= now ||
                key == cue ||
                channel.isNotEmpty && active.channel == channel;
          }).toList();
          for (final key in stopping) {
            await _active.remove(key)!.voice.pause().catchError((_) {});
          }
          while (_active.length >= maximumVoices) {
            final key = _active.keys.first;
            await _active.remove(key)!.voice.pause().catchError((_) {});
          }
          if (!valid()) return;
          final played = await voice.start(
            rate: speed,
            volume: gain,
            canPlay: valid,
          );
          if (played && valid()) {
            _active[cue] = _ActiveVoice(
              voice,
              channel,
              _now() + (cueSeconds[cue]! - (cueStartSeconds[cue] ?? 0)) / speed,
            );
          } else {
            await voice.pause().catchError((_) {});
          }
        });
        await _serial.catchError((_) {});
      } catch (_) {
        // An unavailable speaker or a denied browser sound never blocks play.
      }
    }());
  }

  /// No production caller awaits audio; this helper only drains test fakes.
  Future<void> settle() async {
    await Future<void>.delayed(Duration.zero);
    if (pending.isNotEmpty) await Future.wait(pending.values.toList());
    await Future<void>.delayed(Duration.zero);
    await _serial;
  }

  void pause() {
    epoch++;
    _active.clear();
    _requestGeneration.clear();
    _channelGeneration.clear();
    _lastRequested.clear();
    for (final voice in players.values) {
      unawaited(voice.pause().catchError((_) {}));
    }
  }

  void dispose() {
    if (disposed) return;
    disposed = true;
    epoch++;
    _active.clear();
    for (final voice in players.values) _release(voice);
    players.clear();
  }
}
