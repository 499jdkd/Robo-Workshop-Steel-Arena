import 'package:audioplayers/audioplayers.dart';

/// Only the background music voice owns Android focus. A short coil/impact
/// sound must mix with it instead of requesting a new AUDIOFOCUS_GAIN.
AudioContext gameAudioContext({bool musicOwner = false}) => AudioContext(
  android: AudioContextAndroid(
    contentType: musicOwner
        ? AndroidContentType.music
        : AndroidContentType.sonification,
    usageType: AndroidUsageType.game,
    audioFocus: musicOwner ? AndroidAudioFocus.gain : AndroidAudioFocus.none,
  ),
  iOS: AudioContextIOS(
    category: AVAudioSessionCategory.playback,
    options: {AVAudioSessionOptions.mixWithOthers},
  ),
);
