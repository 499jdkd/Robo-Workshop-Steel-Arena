import 'dart:async';

/// Music belongs to the application, not to a robot or a bounded SFX pool.
abstract class MusicVoice {
  Future<void> load(
    String track, {
    required bool loop,
    required void Function() onComplete,
  });
  Future<bool> start({required bool restart, required bool Function() canPlay});
  Future<void> volume(double gain);
  Future<void> pause();
  Future<void> dispose();
}

final _sessions = Expando<MusicDirector>('game music');
MusicDirector? musicFor(Object backend) => _sessions[backend];
void bindMusic(Object backend, MusicDirector? director) =>
    _sessions[backend] = director;

/// Two long-lived voices: one background loop and one completion-driven jingle.
/// A revision cancels stale loads/fades. No timers run during steady playback.
class MusicDirector {
  MusicDirector({
    required this.background,
    required this.celebration,
    Future<void> Function(Duration)? wait,
    this.onPreference,
  }) : _wait = wait ?? Future<void>.delayed;
  final MusicVoice background, celebration;
  final Future<void> Function(Duration) _wait;
  final void Function(bool enabled)? onPreference;
  String desiredTrack = 'music_workshop', _loadedTrack = '', _lastVictory = '';
  bool enabled = true, active = true, paused = false, disposed = false;
  bool _victory = false, _victoryLoaded = false, _victoryStarted = false;
  bool _bgStarted = false, _bgPlaying = false, _winPlaying = false;
  bool _running = false, _retry = false;
  int _revision = 0, _handled = -1, _victoryGeneration = 0;
  double _bgGain = 0, _winGain = 0;
  Future<void> _work = Future.value();
  Object? lastError;
  bool get celebrating => _victory;
  bool get audible => enabled && active && !paused && !disposed;

  void update({
    required String track,
    required bool sound,
    required bool pause,
    String victory = '',
  }) {
    final next = track == 'arena' ? 'music_arena' : 'music_workshop';
    var changed = next != desiredTrack || sound != enabled || pause != paused;
    desiredTrack = next;
    enabled = sound;
    paused = pause;
    if (!sound && _victory) {
      _victory = false;
      _victoryGeneration++;
      changed = true;
    }
    changed = _requestVictory(victory) || changed;
    if (changed || _handled < 0) _schedule();
  }

  bool _requestVictory(String token) {
    if (disposed || token.isEmpty || token == _lastVictory) return false;
    _lastVictory = token;
    if (!enabled || _victory) return false;
    _victory = true;
    _victoryLoaded = _victoryStarted = false;
    _victoryGeneration++;
    return true;
  }

  /// Emitted by the visible semantic scene when its actual victory phase
  /// begins (also covers PvP), rather than when combat arithmetic resolves.
  void celebrate(String token) {
    if (_requestVictory(token)) _schedule();
  }

  void preference(bool value) {
    if (enabled == value || disposed) return;
    enabled = value;
    if (!value && _victory) {
      _victory = false;
      _victoryGeneration++;
    }
    _schedule();
    onPreference?.call(value);
  }

  void lifecycle(bool value) {
    if (active == value || disposed) return;
    active = value;
    _schedule();
  }

  /// Browsers can deny autoplay before the first gesture. Retry that failure,
  /// rather than restarting an already playing loop on every touch.
  void unlock() {
    if (_retry && audible) {
      _retry = false;
      _schedule();
    }
  }

  void _schedule() {
    if (disposed) return;
    _revision++;
    if (!_running) {
      _running = true;
      _work = _drain();
    }
  }

  Future<void> _drain() async {
    try {
      while (!disposed && _handled != _revision) {
        final revision = _revision;
        try {
          await _reconcile(revision);
          lastError = null;
        } catch (error) {
          lastError = error;
          _retry = true;
        }
        _handled = revision;
      }
    } finally {
      _running = false;
    }
  }

  bool _valid(int revision) => audible && revision == _revision;
  Future<void> _fade(
    MusicVoice voice,
    double to,
    int revision, {
    required bool win,
  }) async {
    final from = win ? _winGain : _bgGain;
    if ((to - from).abs() < .001) return;
    for (var i = 1; i <= 6; i++) {
      if (!_valid(revision)) return;
      final t = i / 6, ease = t * t * (3 - 2 * t);
      final gain = from + (to - from) * ease;
      await voice.volume(gain);
      if (win) {
        _winGain = gain;
      } else {
        _bgGain = gain;
      }
      await _wait(const Duration(milliseconds: 30));
    }
  }

  Future<void> _reconcile(int revision) async {
    if (!audible) {
      await background.pause();
      await celebration.pause();
      _bgPlaying = _winPlaying = false;
      await background.volume(0);
      await celebration.volume(0);
      _bgGain = _winGain = 0;
      return;
    }
    if (_victory) {
      if (_bgPlaying) {
        await _fade(background, 0, revision, win: false);
        if (!_valid(revision)) return;
        await background.pause();
        _bgPlaying = false;
      }
      if (!_victoryLoaded) {
        final generation = _victoryGeneration;
        await celebration.load(
          'music_victory',
          loop: false,
          onComplete: () {
            if (disposed || !_victory || generation != _victoryGeneration)
              return;
            _victory = false;
            _winPlaying = false;
            _winGain = 0;
            _schedule();
          },
        );
        _victoryLoaded = true;
      }
      if (!_valid(revision)) return;
      if (!_winPlaying) {
        await celebration.volume(0);
        _winGain = 0;
        _winPlaying = await celebration.start(
          restart: !_victoryStarted,
          canPlay: () => _valid(revision) && _victory,
        );
        if (!_winPlaying) {
          _retry = true;
          return;
        }
        _victoryStarted = true;
      }
      await _fade(celebration, .28, revision, win: true);
      return;
    }
    if (_loadedTrack != desiredTrack) {
      if (_bgPlaying) await _fade(background, 0, revision, win: false);
      if (!_valid(revision)) return;
      await background.pause();
      _bgPlaying = false;
      final selected = desiredTrack;
      await background.load(selected, loop: true, onComplete: () {});
      _loadedTrack = selected;
      _bgStarted = false;
    }
    if (!_valid(revision) || _victory) return;
    if (!_bgPlaying) {
      await background.volume(0);
      _bgGain = 0;
      _bgPlaying = await background.start(
        restart: !_bgStarted,
        canPlay: () => _valid(revision) && !_victory,
      );
      if (!_bgPlaying) {
        _retry = true;
        return;
      }
      _bgStarted = true;
    }
    await _fade(background, .115, revision, win: false);
  }

  Future<void> settle() async {
    while (_running) {
      await _work;
    }
  }

  Future<void> close() async {
    if (disposed) return;
    disposed = true;
    _revision++;
    await background.dispose();
    await celebration.dispose();
  }
}
