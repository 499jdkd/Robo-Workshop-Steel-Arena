import 'dart:convert';
import 'dart:math' as math;

import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:rive/rive.dart' as rive;

import 'robot/game_motion.dart';
import 'robot/motion_model.dart';
import 'robot/scene_audio.dart';
import 'robot/robot_audio.dart';
import 'robot/robot_profiles.dart';
import 'robot/rig_cache.dart';
import 'robot/signature_motion.dart';
import 'robot/scene_loading.dart';
import 'robot/volt_motion.dart';
import 'robot/volt_model.dart';

/// Semantic Flet events drive native timelines, without Python frame updates.
class GameRiveControl extends StatefulWidget {
  const GameRiveControl({super.key, required this.control});
  final Control control;
  @override
  State<GameRiveControl> createState() => _GameRiveControlState();
}

class _GameRiveControlState extends State<GameRiveControl>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  rive.File? file;
  Future<rive.File?>? loading;
  GameScenePainter? painter;
  RigLease? lease;
  String source = '', renderer = '';
  String reportedScene = '';
  int generation = 0;
  final loadWatch = Stopwatch();
  GameSceneClock? nativeVoltScene;
  late final Ticker nativeTicker;
  Duration? nativePreviousTick;
  bool nativeSelected = false, appActive = true;
  double modelWarmMs = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    appActive =
        WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    nativeTicker = createTicker(advanceNativeVolt);
  }

  void advanceNativeVolt(Duration elapsed) {
    final scene = nativeVoltScene;
    if (!nativeSelected || scene == null) return;
    final previous = nativePreviousTick;
    nativePreviousTick = elapsed;
    final dt = previous == null
        ? 0.0
        : ((elapsed - previous).inMicroseconds / 1000000).clamp(0.0, .04);
    // Only CustomPainter listens to this clock. There is no widget rebuild,
    // Flet event, or Python update on a frame.
    scene.advance(dt);
  }

  void syncNativeTicker() {
    final scene = nativeVoltScene;
    final running =
        nativeSelected &&
        scene != null &&
        !scene.suspended &&
        !scene.hidden &&
        scene.data['paused'] != true;
    if (running && !nativeTicker.isActive) {
      nativePreviousTick = null;
      nativeTicker.start();
    } else if (!running && nativeTicker.isActive) {
      nativeTicker.stop();
      nativePreviousTick = null;
      scene?.audio.pause();
    }
  }

  void dropRive() {
    generation++; // A late asynchronous load can no longer become this scene.
    painter?.dispose();
    painter = null;
    file = null;
    loading = null;
    source = renderer = '';
    final previous = lease;
    lease = null;
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.release());
  }

  void dropNativeVolt() {
    nativeSelected = false;
    syncNativeTicker();
    nativeVoltScene?.dispose();
    nativeVoltScene = null;
    nativePreviousTick = null;
  }

  Widget nativeVolt(BuildContext context, Map<String, dynamic> data) {
    if (!nativeSelected) {
      dropRive();
      reportedScene = '';
      nativeSelected = true;
      nativeVoltScene = GameSceneClock();
      final watch = Stopwatch()..start();
      warmVoltModel();
      modelWarmMs = watch.elapsedMicroseconds / 1000;
    }
    final scene = nativeVoltScene!;
    scene.update(data);
    scene.reduced =
        MediaQuery.disableAnimationsOf(context) ||
        data['reducedEffects'] == true;
    scene.hidden =
        !TickerMode.valuesOf(context).enabled || !widget.control.visible;
    scene.suspended = !appActive;
    if (data['sound'] != false) scene.audio.configure(widget.control.backend);
    syncNativeTicker();
    final sceneKey = 'native-volt|${data['expanded']}|${data['demonstration']}';
    return LayoutControl(
      control: widget.control,
      child: LayoutBuilder(
        builder: (context, constraints) {
          scene.viewport = constraints.biggest;
          if (scene.playerVoltFrame == null) {
            // A paused/hidden first mount still needs a static model. Sampling
            // time zero never advances motion, consumes resources or plays a cue.
            final savedData = scene.data,
                hidden = scene.hidden,
                suspended = scene.suspended;
            scene.data = {...savedData, 'paused': false, 'sampleOnly': true};
            scene.hidden = scene.suspended = false;
            scene.advance(0);
            scene.data = savedData;
            scene.hidden = hidden;
            scene.suspended = suspended;
          } else {
            scene.advance(0);
          }
          return GameSceneView(
            nativeScene: scene,
            onRobotTap: () => widget.control.triggerEvent('robot_tap'),
            onFirstPaint: () {
              if (!mounted ||
                  !nativeSelected ||
                  nativeVoltScene != scene ||
                  reportedScene == sceneKey ||
                  !widget.control.getBool('report_ready', false)!)
                return;
              reportedScene = sceneKey;
              widget.control.triggerEvent('ready', {
                'data': {
                  'robot': 'volt',
                  'enemy': '',
                  'renderer': 'flutter',
                  'model_renderer': 'flutter-canvas-articulated',
                  'rig_load_ms': 0,
                  'model_warm_ms': modelWarmMs,
                },
              });
            },
          );
        },
      ),
    );
  }

  void load() {
    final src = widget.control.getString('src', '')!;
    final requested = widget.control.getString('renderer', 'auto')!;
    // Both factories use the same native Rive artboard/state machine. The
    // Flutter compositor avoids the platform-texture path on Android/iOS.
    final engine = requested == 'auto'
        ? (!kIsWeb &&
                  {
                    TargetPlatform.android,
                    TargetPlatform.iOS,
                  }.contains(defaultTargetPlatform)
              ? 'flutter'
              : 'rive')
        : requested;
    if (src == source && engine == renderer) return;
    source = src;
    renderer = engine;
    final current = ++generation;
    loadWatch
      ..reset()
      ..start();
    painter?.dispose();
    painter = null;
    final previous = lease;
    file = null;
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.release());
    final asset = widget.control.backend.getAssetSource(src);
    lease = acquireRig(
      '${asset.path}|$engine',
      () => rive.RiveNative.init().then((_) {
        final factory = engine == 'flutter'
            ? rive.Factory.flutter
            : rive.Factory.rive;
        return asset.isFile
            ? rive.File.path(asset.path, riveFactory: factory)
            : rive.File.url(asset.path, riveFactory: factory);
      }),
    );
    loading = lease!.future.then((value) {
      if (!mounted || current != generation) {
        return null;
      }
      loadWatch.stop();
      return file = value;
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    appActive = state == AppLifecycleState.resumed;
    nativeVoltScene?.suspended = !appActive;
    nativeVoltScene?.audio.pause();
    nativePreviousTick = null;
    syncNativeTicker();
    painter?.scene.suspended = state != AppLifecycleState.resumed;
    painter?.scene.audio.pause();
    painter?.resetTime = true;
    if (state == AppLifecycleState.resumed) painter?.scheduleRepaint();
  }

  @override
  void didHaveMemoryPressure() {
    clearIdleRigCache();
    clearVoltModelCaches();
  }

  @override
  Widget build(BuildContext context) {
    final data =
        jsonDecode(widget.control.getString('payload', '{}')!)
            as Map<String, dynamic>;
    if (data['robot'] == 'volt' && data['arena'] != true)
      return nativeVolt(context, data);
    if (nativeSelected) {
      dropNativeVolt();
      reportedScene = '';
    }
    load();
    return LayoutControl(
      control: widget.control,
      child: FutureBuilder<rive.File?>(
        key: ValueKey('$source|$renderer'),
        future: loading,
        builder: (context, snapshot) {
          if (snapshot.hasError ||
              (snapshot.connectionState == ConnectionState.done &&
                  snapshot.data == null)) {
            return const Center(
              child: Icon(
                Icons.smart_toy_outlined,
                size: 74,
                color: Color(0xFF6A89A2),
              ),
            );
          }
          final value = snapshot.data;
          if (value == null) return const SceneLoadingRobot();
          final p = painter ??= GameScenePainter(value);
          final data =
              jsonDecode(widget.control.getString('payload', '{}')!)
                  as Map<String, dynamic>;
          p.scene.reduced =
              MediaQuery.disableAnimationsOf(context) ||
              data['reducedEffects'] == true;
          p.scene.hidden = !TickerMode.valuesOf(context).enabled;
          p.scene.update(data);
          final sceneKey =
              '$source|$renderer|${data['robot']}|${data['enemy']}|${data['arena']}|${data['expanded']}';
          if (widget.control.getBool('report_ready', false)! &&
              reportedScene != sceneKey) {
            p.onFirstPaint = () {
              if (!mounted || reportedScene == sceneKey) return;
              reportedScene = sceneKey;
              widget.control.triggerEvent('ready', {
                'data': {
                  'robot': data['robot'],
                  'enemy': data['arena'] == true ? data['enemy'] : '',
                  'renderer': renderer,
                  'model_renderer': data['robot'] == 'volt'
                      ? 'flutter-canvas-articulated'
                      : 'rive-artboard',
                  'rig_load_ms': loadWatch.elapsedMicroseconds / 1000,
                },
              });
            };
          }
          if (data['sound'] != false)
            p.scene.audio.configure(widget.control.backend);
          return LayoutBuilder(
            builder: (context, constraints) {
              p.scene.viewport = constraints.biggest;
              return GameSceneView(
                file: value,
                painter: p,
                onRobotTap: () => widget.control.triggerEvent('robot_tap'),
              );
            },
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    generation++;
    WidgetsBinding.instance.removeObserver(this);
    nativeTicker.dispose();
    nativeVoltScene?.dispose();
    nativeVoltScene = null;
    painter?.dispose();
    final previous = lease;
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.release());
    super.dispose();
  }
}

class _VoltPlayback {
  String action = '';
  double cueT = -.001, blendAt = -99;
  GamePose? from;
  VoltFrame? frame;
  VoltFrame? fromFrame;
  void reset() {
    action = '';
    cueT = -.001;
    blendAt = -99;
    from = null;
    frame = null;
    fromFrame = null;
  }
}

class GameSceneClock extends ChangeNotifier {
  GameSceneClock({
    void Function(RobotAudioCue)? onCharacterCue,
    int? reactionSeed,
    SceneAudio? sceneAudio,
  }) : audio = sceneAudio ?? SceneAudio(),
       _reactionRandom = math.Random(reactionSeed) {
    characterSounds = RobotSoundDirector(
      onCharacterCue ??
          (cue) => audio.play(
            cue.name,
            rate: cue.rate,
            volume: cue.volume,
            channel: cue.channel,
          ),
    );
  }
  Map<String, dynamic> data = {};
  final player = GameActor(), enemy = GameActor()..facing = -1;
  final effects = GameEffects();
  void Function()? pendingBurst;
  GamePose? previousPlayer, previousEnemy;
  final SceneAudio audio;
  late final RobotSoundDirector characterSounds;
  int _localSoundSerial = 0;
  final math.Random _reactionRandom;
  final _reactionBag = <String>[];
  final _voltPlayer = _VoltPlayback(), _voltEnemy = _VoltPlayback();
  VoltFrame? get playerVoltFrame => _voltPlayer.frame;
  VoltFrame? get enemyVoltFrame => _voltEnemy.frame;
  bool get isVolt => data['robot'] == 'volt';
  double? _voltOutcomeAt;
  Size viewport = const Size(390, 294);
  double clock = 0, age = 0, zoom = 1, zoomTarget = 1, patrol = 0;
  double localAge = 99, walkAge = 99, walkDuration = 1;
  double walkFrom = .5, walkTarget = .5, lastTap = -10;
  int tapBurst = 0, reactionIndex = 0;
  String localAction = '';
  bool manualPosition = false;
  Offset pan = Offset.zero, gaze = Offset.zero;
  bool reduced = false, suspended = false, inspecting = false, hidden = false;
  bool get arena => data['arena'] == true;
  bool get demonstration => data['demonstration'] == true;
  bool get expanded => data['expanded'] == true;
  String get phase => data['phase'] as String? ?? 'idle';
  String get action => data['action'] as String? ?? 'idle';
  String get weapon => data['weapon'] as String? ?? 'plasma';
  String get enemyWeapon => data['enemyWeapon'] as String? ?? 'plasma';
  double get scale => math.min(
    viewport.height *
        (arena ? .64 : .68) /
        330 *
        (signatureVisible &&
                {'falcon', 'phoenix', 'storm', 'volt'}.contains(signatureId)
            ? 1 - .16 * math.sin(signatureT * math.pi)
            : 1),
    // Reserve the complete 420px artboard, including deployed long weapons,
    // instead of fitting only the 240px chassis and cropping its extremities.
    viewport.width *
        (arena
            ? .42
            : demonstration
            ? .72
            : .80) /
        420,
  );
  double get floor => viewport.height * (arena ? .84 : .86);
  bool get playerShot =>
      (!arena && localAction == 'attack' && localAge >= .4 && localAge < 1.3) ||
      ({'flight', 'counter-flight'}.contains(phase) &&
          {'attack', 'special'}.contains(action)) ||
      phase == 'counter-flight';
  bool get enemyShot =>
      phase == 'enemy-flight' &&
      {'attack', 'special'}.contains(data['enemyAction'] ?? 'attack') &&
      data['stunned'] != true &&
      data['intent'] != 'windup';
  String get activeWeapon => enemyShot ? enemyWeapon : weapon;
  bool get visibleShot =>
      (playerShot || enemyShot) &&
      !{'shield', 'charge', 'dodge'}.contains(activeWeapon);
  double get progress => !arena
      ? unit((localAge - .4) / .9)
      : unit(
          age /
              (phase == 'counter-flight'
                  ? .65
                  : enemyShot
                  ? .72
                  : (data['flightSeconds'] as num? ?? .72)),
        );
  String get combatAction => data['combatAction'] as String? ?? action;
  String get activeCombatAction => enemyShot
      ? data['enemyCombatAction'] as String? ?? 'attack'
      : arena
      ? combatAction
      : localAction;
  bool get signatureVisible => arena
      ? ({'special', 'ultimate'}.contains(combatAction) &&
                {'approach', 'flight', 'impact'}.contains(phase)) ||
            (enemyShot &&
                {'special', 'ultimate'}.contains(data['enemyCombatAction']))
      : {'special', 'ultimate'}.contains(localAction) &&
            localAge < (isVolt ? voltActionSeconds[localAction]! : 2.25);
  bool get ultimate => activeCombatAction == 'ultimate';
  String get signatureId =>
      data[enemyShot ? 'enemy' : 'robot'] as String? ?? 'spark';
  double get signatureT => !arena
      ? unit(localAge / 2.25)
      : phase == 'approach'
      ? unit(age / (combatAction == 'ultimate' ? .72 : .55)) * .28
      : phase == 'impact'
      ? .83 + unit(age / .38) * .17
      : .28 + progress * .55;
  double get impact =>
      ((phase == 'impact' && (data['damage'] as num? ?? 0) > 0) ||
          (phase == 'reply' && (data['incoming'] as num? ?? 0) > 0) ||
          phase == 'counter-hit')
      ? math.exp(-age * 7)
      : 0;
  double get voltCamera =>
      math.max(playerVoltFrame?.camera ?? 0, enemyVoltFrame?.camera ?? 0);
  Offset get shake => reduced
      ? Offset.zero
      : Offset(
          math.sin(age * 103) * (ultimate ? 12 : 6) * impact +
              math.sin(clock * 91) * 3.5 * voltCamera,
          math.cos(age * 137) * (ultimate ? 7 : 3) * impact +
              math.cos(clock * 113) * 2 * voltCamera,
        );

  void update(Map<String, dynamic> next) {
    final contextChanged =
        next['robot'] != data['robot'] ||
        next['arena'] != data['arena'] ||
        next['demonstration'] != data['demonstration'];
    if (contextChanged) {
      patrol = 0;
      zoom = zoomTarget = 1;
      pan = Offset.zero;
      gaze = Offset.zero;
      inspecting = false;
      manualPosition = false;
      localAction = '';
      localAge = walkAge = 99;
      tapBurst = reactionIndex = 0;
      lastTap = clock - 10;
      audio.pause();
      pendingBurst = null;
      characterSounds.reset();
      _localSoundSerial = 0;
      _reactionBag.clear();
      previousPlayer = previousEnemy = null;
      _voltPlayer.reset();
      _voltEnemy.reset();
      _voltOutcomeAt = null;
      player.facing = 1;
      effects.particles.clear();
    }
    final changed = contextChanged || next['event'] != data['event'];
    final previousAction = action;
    final keepFeeding =
        !contextChanged &&
        !arena &&
        previousAction == 'feed' &&
        age < 1.4 &&
        next['action'] == 'joy';
    final keepReaction =
        !contextChanged &&
        !arena &&
        previousAction == next['action'] &&
        age < .5;
    data = next;
    if (next['result'] != 'win' && next['result'] != 'loss')
      _voltOutcomeAt = null;
    if (keepFeeding) data['action'] = 'feed';
    audio.enabled = next['sound'] != false;
    player.mobility = next['mobility'] as String? ?? 'tracks';
    enemy.mobility = next['enemyMobility'] as String? ?? 'tracks';
    if (!changed || keepFeeding || keepReaction) return;
    previousPlayer = contextChanged ? null : player.pose;
    previousEnemy = contextChanged ? null : enemy.pose;
    age = 0;
    final tapEcho =
        isVolt &&
        !arena &&
        !demonstration &&
        combatAction == 'joy' &&
        localAction.isNotEmpty &&
        localAge < (voltActionSeconds[localAction] ?? 0);
    if (!arena &&
        !tapEcho &&
        ({'attack', 'special', 'ultimate', 'guard'}.contains(combatAction) ||
            isVolt && voltActionSeconds.containsKey(combatAction))) {
      showcase(combatAction);
    }
    if (arena) {
      if (phase == 'impact' || phase == 'reply' || phase == 'counter-hit') {
        final guarded = phase == 'reply' && action == 'guard';
        final damage =
            next[phase == 'reply' ? 'incoming' : 'damage'] as num? ?? 0;
        if (damage > 0 || guarded) {
          audio.play(guarded ? 'shield' : 'impact');
          final target = phase == 'reply' ? player : enemy;
          if (!reduced) {
            pendingBurst = () {
              final point = Offset(target.center, floor - 140 * scale);
              effects.burst(
                point,
                guarded ? const Color(0xFF75DCFF) : const Color(0xFFFFD775),
                count: 40,
              );
              if ((phase == 'reply' ? enemyWeapon : weapon) == 'rocket')
                effects.burst(
                  point,
                  const Color(0xFF97A3B2),
                  smoke: true,
                  count: 22,
                );
            };
          }
        }
      }
    } else if (action == 'feed') {
      audio.play('feed');
      if (!reduced)
        pendingBurst = () => effects.burst(
          Offset(player.center, floor - 190 * scale),
          const Color(0xFF6FEAD2),
          count: 14,
        );
    }
  }

  void advance(double dt) {
    if (suspended || hidden || data['paused'] == true) return;
    clock += dt;
    age += dt * (arena ? (data['animationSpeed'] as num? ?? 1).clamp(1, 2) : 1);
    localAge += dt;
    walkAge += dt;
    effects.limit = reduced
        ? 0
        : viewport.shortestSide < 400
        ? 48
        : 96;
    effects.advance(dt);
    final s = scale;
    final lastPlayer = player.pose, lastEnemy = enemy.pose;
    player.pose = GamePose(clock);
    enemy.pose = GamePose(clock + .7);
    double px = viewport.width * (arena ? .25 : .5), ex = viewport.width * .75;
    final p = player.pose, e = enemy.pose;
    if (!arena) {
      final reacting =
          (age < (action == 'feed' ? 1.7 : .95) && action != 'idle') ||
          localAge < 2.25 ||
          (isVolt && localAction == 'defeat');
      final id = data['robot'];
      final role = robotProfiles[id]?['class'];
      final speed = role == 'tank'
          ? 0.64
          : role == 'scout'
          ? 1.45
          : role == 'support'
          ? 0.85
          : 1.0;
      if (!inspecting && !reduced && !reacting) patrol += dt * speed;
      final span = math.max(
        0,
        (viewport.width - 420 * s - 16) * (expanded ? .36 : .22),
      );
      if (manualPosition) {
        px =
            viewport.width *
            (walkFrom +
                (walkTarget - walkFrom) * smooth(walkAge / walkDuration));
      } else if (demonstration) {
        px = viewport.width * .4;
      } else {
        px += span * math.sin(patrol * .72);
      }
      if (!manualPosition && !inspecting && !reacting && !reduced)
        player.facing = math.cos(patrol * .72) < 0 ? -1 : 1;
      if (reacting) p.emotion(action, age);
      if (localAge < 1.6 &&
          !{'attack', 'special', 'ultimate', 'guard'}.contains(localAction)) {
        p.emotion(localAction, localAge);
      }
      if (localAction == 'guard' && localAge < 2.25) {
        p.shield = math.sin(math.pi * unit(localAge / 2.25));
        p.armR = -1.3;
      }
      if (localAction == 'attack' && localAge < 1.8) {
        if (localAge < .4)
          p.prepare(weapon, localAge);
        else
          p.fire(weapon, localAge - .4);
      }
      if (!reacting && !inspecting && !reduced) {
        final seed = (id as String? ?? 'spark').codeUnits.fold<int>(
          0,
          (sum, n) => sum + n,
        );
        final beat = (clock + seed % 11) % 29;
        if (beat > 10 && beat < 11.6) p.emotion('inspect', beat - 10);
        if (beat > 19 && beat < 20.7)
          p.emotion(data['idleEmotion'] as String? ?? 'dance', beat - 19);
        if (beat > 25 && beat < 27.25 && !demonstration) {
          _localSoundSerial++;
          localAction = 'attack';
          localAge = beat - 25;
          player.facing = 1;
        }
      }
    } else {
      if (phase == 'approach') {
        if ({'attack', 'special'}.contains(action)) {
          p.prepare(weapon, age);
          e.emotion('fear', age);
        }
        if (action == 'guard') {
          p.shield = smooth(age / .2);
          p.armR = -1.3;
          p.smile = 0;
          p.focus = 1;
        }
        if (action == 'charge') {
          p.aura = .8;
          p.emotion('anger', age);
          p.armL = .8;
          p.armR = -.8;
        }
        if (action == 'dodge') {
          p.x -= 36 * smooth(age / .3);
          p.y -= 12;
          p.rotation = -.18;
        }
      }
      if (playerShot) {
        p.fire(weapon, age);
        if (combatAction == 'quick') {
          p.x += 38 * math.sin(progress * math.pi);
          p.body += .18;
        }
        if (combatAction == 'pierce') {
          p.eyeY = .35;
          p.x -= 18 * math.exp(-age * 12);
        }
        if (combatAction == 'burst') {
          p.x -= 14 * math.sin(age * 32);
          p.foreR += .18 * math.sin(age * 32);
        }
        if (!isVolt && (weapon == 'fist' || weapon == 'sword'))
          px += math.max(0, ex - px - 185 * s) * smooth(age / .55);
        e.emotion('fear', age);
      }
      if (phase == 'impact') {
        if (!isVolt && (weapon == 'fist' || weapon == 'sword'))
          px += math.max(0, ex - px - 185 * s) * (1 - smooth(age / .45));
        if ({'attack', 'special'}.contains(action)) p.fire(weapon, .95 + age);
        if ((data['damage'] as num? ?? 0) > 0)
          e.hit(age, unit((data['damage'] as num) / 40));
        if (weapon == 'shield') p.shield = 1;
        if (weapon == 'repair') {
          p.aura = .8;
          p.emotion('joy', age);
        }
      }
      if (enemyShot) {
        e.fire(enemyWeapon, age);
        if (data['enemy'] != 'volt' &&
            (enemyWeapon == 'fist' || enemyWeapon == 'sword'))
          ex -= math.max(0, ex - px - 185 * s) * smooth(age / .55);
        if (action == 'guard') {
          p.shield = 1;
          p.armR = -1.2;
        } else if (data['dodged'] == true) {
          px -= 35 * math.sin(progress * math.pi);
          p.rotation = -.23;
          p.y = -15 * math.sin(progress * math.pi);
        } else {
          p.emotion('fear', age);
        }
      }
      if (phase == 'enemy-flight' &&
          (data['intent'] == 'windup' || data['enemyAction'] == 'charge')) {
        e.aura = .85;
        e.emotion('anger', age);
      }
      if (phase == 'enemy-flight' && data['enemyAction'] == 'guard') {
        e.shield = smooth(age / .2);
        e.armR = -1.2;
      }
      if (phase == 'enemy-flight' && data['enemyAction'] == 'charge') {
        e.aura = .85;
        e.emotion('anger', age);
      }
      if (phase == 'reply') {
        if (data['enemy'] != 'volt' &&
            (enemyWeapon == 'fist' || enemyWeapon == 'sword'))
          ex -= math.max(0, ex - px - 185 * s) * (1 - smooth(age / .45));
        if ((data['incoming'] as num? ?? 0) > 0)
          p.hit(age, unit((data['incoming'] as num) / 35));
        if (action == 'guard') p.shield = math.exp(-age * 3);
        if (data['dodged'] == true) p.emotion('joy', age);
      }
      if (phase == 'counter-hit') e.hit(age, .8);
      if (phase == 'victory' || (phase == 'idle' && data['result'] == 'win')) {
        p.emotion('victory', age);
        e.emotion('defeat', age);
      }
      if (phase == 'idle' && data['result'] == 'loss') {
        p.emotion('defeat', age);
        e.emotion('victory', age);
      }
    }
    if (player.mobility == 'hover') p.y -= 10 + 7 * math.sin(clock * 3);
    if (enemy.mobility == 'hover') e.y -= 10 + 7 * math.sin(clock * 3 + 1);
    if (player.mobility == 'flight') p.y -= 22 + 8 * math.sin(clock * 2.4);
    if (enemy.mobility == 'flight') e.y -= 22 + 8 * math.sin(clock * 2.4 + 1);
    if (!reduced &&
        !{'impact', 'reply', 'counter-hit'}.contains(phase) &&
        age < .14) {
      final blend = smooth(age / .14);
      if (previousPlayer != null && !isVolt)
        p.blendFrom(previousPlayer!, blend);
      if (previousEnemy != null && data['enemy'] != 'volt')
        e.blendFrom(previousEnemy!, blend);
    }
    if (!arena) {
      final gear = data['equipped'];
      if (gear is List && gear.isNotEmpty && p.weapon.isEmpty) {
        p.weapon = gear.first as String;
        p.deploy = .58;
        p.armR = -.85;
      }
    }
    double inside(double x, GameActor actor, bool volt, List gear) {
      if (!volt) {
        final edge = 210 * s + (arena ? viewport.width * .055 : 8);
        return viewport.width > 2 * edge
            ? x.clamp(edge, viewport.width - edge)
            : viewport.width / 2;
      }
      // Volt's compact built-in emitter does not occupy the generic 420px
      // weapon envelope. That envelope erased almost the entire dodge on a
      // portrait phone. Reserve extra space only in front of mounted gear.
      final front = gear.isEmpty ? 140.0 : 210.0;
      final left = (actor.facing < 0 ? front : 140.0) * s + 8;
      final right = (actor.facing < 0 ? 140.0 : front) * s + 8;
      return viewport.width > left + right
          ? x.clamp(left, viewport.width - right)
          : viewport.width / 2;
    }

    void style(GameActor actor, String id) {
      final pose = actor.pose, f = pose.extra;
      final profile = robotProfiles[id] ?? robotProfiles['spark']!;
      final construction = profile['construction'] as String;
      pose.head +=
          .04 *
          math.sin(
            clock * .7 + id.codeUnits.fold<int>(0, (sum, n) => sum + n) * .13,
          );
      pose.headY += (profile['headY'] as num).toDouble() + 117;
      for (var i = 0; i < 16; i++) {
        final stride = actor.motor.distance / 22;
        f['joint$i'] = math.sin(stride + (i % 2) * math.pi) * .35;
        if (actor.mobility == 'hexapod')
          f['joint$i'] = math.sin(stride + i * math.pi) * .42;
        if (actor.mobility == 'quadruped')
          f['joint$i'] =
              math.sin(stride + [0, math.pi, math.pi, 0][i % 4]) * .36;
        if (i >= 8)
          f['joint$i'] =
              math.max(0, math.sin(stride + (i % 2) * math.pi)) * .55;
        if (actor.mobility == 'flight')
          f['joint$i'] = math.sin(clock * 6 + i * math.pi) * .4;
        if ({
          'gyro',
          'reactor',
          'sun',
          'clock',
          'storm',
          'magnet',
          'hologram',
        }.contains(construction))
          f['joint$i'] =
              i * math.pi / 6 + clock * (construction == 'clock' ? .14 : .32);
        if (construction == 'octopus')
          f['joint$i'] = math.sin(clock * 2.5 - i * .65) * .23;
        if (construction == 'serpent')
          f['joint$i'] = math.sin(clock * 3.3 - i * .7) * .28;
        if (construction == 'medic' && i >= 4 && i < 8)
          f['joint$i'] = clock * 24;
        if (construction == 'driller' && i == 4)
          f['joint$i'] = clock * (phase == 'flight' ? 35 : 8);
        if (construction == 'transformer' && i >= 2 && i <= 3)
          f['joint$i'] = (i == 2 ? -1 : 1) * (.16 + pose.deploy * .8);
      }
      for (var i = 0; i < 8; i++)
        f['segmentY$i'] = 95 + math.sin(clock * 3.3 - i * .7) * 7;
      f['joint14'] = actor.motor.distance / 17 + clock * .5;
      final heavy = id == 'forge' || id == 'aegis';
      f['tracks'] = actor.mobility == 'tracks' ? 1 : 0;
      f['hover'] = actor.mobility == 'hover' ? 1 : 0;
      f['legs'] = actor.mobility == 'legs' ? 1 : 0;
      f['wheels'] = actor.mobility == 'wheels' ? 1 : 0;
      f['bodyscaleX'] = heavy
          ? 1.24
          : id == 'volt'
          ? .82
          : 1;
      f['bodyscaleY'] = heavy
          ? 1.12
          : id == 'nova'
          ? .85
          : 1;
      f['headscaleX'] = id == 'forge'
          ? .88
          : id == 'flora'
          ? .93
          : 1;
      f['headscaleY'] = id == 'forge'
          ? .82
          : id == 'glacier'
          ? .86
          : 1;
      f['leaf'] = id == 'flora' ? 1 : 0;
      f['fins'] = id == 'glacier' || id == 'nova' ? 1 : 0;
      f['sun'] = id == 'solar' ? 1 : 0;
      f['gearAngle'] = actor.motor.distance / 17 + clock * (heavy ? .25 : .7);
      f['gunRotor'] = clock * (pose.weapon == 'machinegun' ? 35 : 14);
      for (var i = 0; i < 3; i++) {
        f['barrel${i}X'] = math.sin(clock * 32 + i * math.pi * 2 / 3) * 13;
      }
      final stride = math.sin(actor.motor.distance / 18);
      f['legL'] = stride * .4;
      f['legR'] = -stride * .4;
      f['jet'] = 1 + .22 * math.sin(clock * (id == 'volt' ? 15 : 8));
      if (!arena && age > 1.7) {
        if (id == 'flora') pose.head += math.sin(clock * 2) * .12;
        if (id == 'nova') {
          pose.armL += .3 * math.sin(clock * 2);
          pose.foreL = -.6;
        }
        if (id == 'forge') {
          pose.body += .05 * math.sin(clock);
          pose.head *= .6;
        }
        if (id == 'aegis') {
          pose.armL = .35;
          pose.foreL = -.5;
        }
        if (id == 'solar') pose.armR -= .3 * math.sin(clock * 3);
        if (id == 'volt') pose.head += .1 * math.sin(clock * 5);
      }
    }

    style(player, data['robot'] as String? ?? 'spark');
    if (arena) style(enemy, data['enemy'] as String? ?? 'flora');
    if (signatureVisible && signatureId != 'volt') {
      signaturePose(
        enemyShot ? e : p,
        signatureId,
        signatureT,
        ultimate: ultimate,
      );
    }
    if (isVolt)
      _animateVolt(player, lastPlayer, _voltPlayer, dt, opponent: false);
    if (arena && data['enemy'] == 'volt')
      _animateVolt(enemy, lastEnemy, _voltEnemy, dt, opponent: true);
    player.travel(
      inside(
        px + p.x * s * player.facing,
        player,
        isVolt,
        data['equipped'] as List? ?? const [],
      ),
      s,
      dt,
    );
    if (arena) {
      enemy.travel(
        inside(
          ex - e.x * s,
          enemy,
          data['enemy'] == 'volt',
          data['enemyEquipped'] as List? ?? const [],
        ),
        s,
        dt,
      );
    }
    final modules = (data['modules'] as List? ?? const []).cast<String>();
    final equipment = (data['equipped'] as List? ?? const []).cast<String>();
    final second = equipment.length > 1 ? equipment[1] : '';
    player.pose.extra['secondaryPods'] = {'rocket', 'grenade'}.contains(second)
        ? 1
        : 0;
    player.pose.extra['secondaryBlade'] =
        {'sword', 'fist', 'drill', 'disc'}.contains(second) ? 1 : 0;
    player.pose.extra['secondaryOrb'] =
        {'shield', 'drone', 'repair', 'emp'}.contains(second) ? 1 : 0;
    player.pose.extra['secondaryGun'] =
        second.isNotEmpty &&
            !{
              'rocket',
              'grenade',
              'sword',
              'fist',
              'drill',
              'disc',
              'shield',
              'drone',
              'repair',
              'emp',
            }.contains(second)
        ? 1
        : 0;
    for (final entry in {
      'modArmor': const ['alloy', 'ceramic'],
      'modCore': const ['reactor', 'capacitor'],
      'modDrive': const ['servo', 'gyroscope'],
      'modDefense': const ['barrier', 'insulator'],
      'modGadget': const ['scope', 'overdrive'],
    }.entries) {
      player.pose.extra[entry.key] = modules.any(entry.value.contains) ? 1 : 0;
    }
    pendingBurst?.call();
    pendingBurst = null;
    final autoZoom = reduced
        ? 1.0
        : arena && (phase == 'approach' || visibleShot)
        ? (signatureVisible && ultimate
              ? 1.07
              : activeWeapon == 'sniper'
              ? 1.06
              : 1.025)
        : 1.0;
    final cinematic =
        1 +
        .035 *
            math.max(
              playerVoltFrame?.cameraZoom ?? 0,
              enemyVoltFrame?.cameraZoom ?? 0,
            );
    final target = zoomTarget * math.max(autoZoom, cinematic);
    zoom += (target - zoom) * (1 - math.exp(-10 * dt));
    _sampleCharacterSounds();
    notifyListeners();
  }

  ({String action, double t, String token}) _localAudioPresentation() {
    final localToken = 'local:$_localSoundSerial';
    if (isVolt) {
      final frame = playerVoltFrame;
      return (
        action: frame?.action ?? 'idle',
        t: frame?.t ?? 0,
        token: frame?.action == localAction
            ? localToken
            : 'ambient:${(clock / 23).floor()}',
      );
    }
    if (localAction == 'attack' && localAge < 1.8)
      return (action: 'attack', t: unit(localAge / 1.4), token: localToken);
    if ({'special', 'ultimate', 'guard'}.contains(localAction) &&
        localAge < 2.25)
      return (action: localAction, t: unit(localAge / 2.25), token: localToken);
    if (localAction.isNotEmpty && localAge < 1.6)
      return (action: localAction, t: unit(localAge / 1.6), token: localToken);
    final reacting = age < (action == 'feed' ? 1.7 : .95) && action != 'idle';
    if (reacting)
      return (
        action: action,
        t: unit(age / (action == 'feed' ? 1.7 : .95)),
        token: 'event:${data['event']}',
      );
    if (manualPosition && walkAge < walkDuration)
      return (
        action: 'move',
        t: unit(walkAge / walkDuration),
        token: localToken,
      );
    if (!inspecting && !reduced && localAge >= 2.25) {
      final id = data['robot'] as String? ?? 'spark';
      final seed = id.codeUnits.fold<int>(0, (sum, n) => sum + n);
      final shifted = clock + seed % 11;
      final beat = shifted % 29;
      final token = 'ambient:${(shifted / 29).floor()}';
      if (beat > 10 && beat < 11.6)
        return (action: 'inspect', t: (beat - 10) / 1.6, token: token);
      if (beat > 19 && beat < 20.7)
        return (
          action: data['idleEmotion'] as String? ?? 'dance',
          t: (beat - 19) / 1.7,
          token: token,
        );
    }
    return (action: 'idle', t: 0.0, token: localToken);
  }

  ({String action, double t}) _battleAudioPresentation(bool opponent) {
    if ({'victory', 'idle'}.contains(phase) &&
        {'win', 'loss'}.contains(data['result'])) {
      _voltOutcomeAt ??= clock;
      final won = data['result'] == 'win';
      return (
        action: (opponent ? !won : won) ? 'victory' : 'defeat',
        t: unit((clock - _voltOutcomeAt!) / 2.2),
      );
    }
    if (opponent) {
      final name = data['enemyCombatAction'] as String? ?? 'attack';
      if (phase == 'enemy-flight' && data['stunned'] != true) {
        if (data['intent'] == 'windup' || data['enemyAction'] == 'charge')
          return (action: 'charge', t: unit(age / .72));
        return (action: name, t: .28 + .55 * unit(age / .72));
      }
      if (phase == 'reply' && data['stunned'] != true)
        return (action: name, t: .83 + .17 * unit(age / .25));
      return (action: 'idle', t: 0.0);
    }
    final name = phase.startsWith('counter-') ? 'attack' : combatAction;
    final prepare = (data['prepareSeconds'] as num? ?? .4).toDouble();
    final recover = (data['impactSeconds'] as num? ?? .25).toDouble();
    if ({'guard', 'dodge', 'charge'}.contains(name)) {
      if (phase == 'approach')
        return (action: name, t: .3 * unit(age / prepare));
      if (phase == 'impact')
        return (action: name, t: .3 + .1 * unit(age / recover));
      if (phase == 'enemy-flight')
        return (action: name, t: .4 + .4 * unit(age / .72));
      if (phase == 'reply') return (action: name, t: .8 + .2 * unit(age / .25));
    } else {
      if (phase == 'approach')
        return (action: name, t: .28 * unit(age / prepare));
      if (phase == 'flight' || phase == 'counter-flight')
        return (action: name, t: .28 + .55 * progress);
      if (phase == 'impact' || phase == 'counter-hit')
        return (action: name, t: .83 + .17 * unit(age / recover));
    }
    return (action: 'idle', t: 0.0);
  }

  void _sampleCharacterSounds() {
    if (data['sampleOnly'] == true) return;
    final audible = audio.enabled && !audio.muted;
    if (!arena) {
      final sample = _localAudioPresentation();
      if (sample.action == 'victory' && sample.t >= .08)
        audio.celebrate('preview:${data['event']}:$_localSoundSerial');
      // Volt has his own attack/charge timeline. His previously silent social
      // reactions share this director; feeding already has its saved-game cue.
      final ownedByDirector =
          !isVolt ||
          {'joy', 'anger', 'dance', 'inspect', 'move'}.contains(sample.action);
      characterSounds.sample(
        slot: 'player',
        robot: data['robot'] as String? ?? 'spark',
        action: sample.action,
        t: sample.t,
        token: sample.token,
        weapon: weapon,
        enabled: audible && ownedByDirector && sample.action != 'feed',
      );
      return;
    }
    final event = (data['event'] ?? '').toString().split(':').take(2).join(':');
    if ({'victory', 'idle'}.contains(phase) && data['result'] == 'win')
      audio.celebrate(
        'battle:${(data['event'] ?? '').toString().split(':').first}',
      );
    for (final opponent in [false, true]) {
      final id = data[opponent ? 'enemy' : 'robot'] as String? ?? 'spark';
      if (id == 'volt') continue;
      final sample = _battleAudioPresentation(opponent);
      characterSounds.sample(
        slot: opponent ? 'enemy' : 'player',
        robot: id,
        action: sample.action,
        t: sample.t,
        token: event,
        weapon: opponent ? enemyWeapon : weapon,
        enabled: audible,
      );
    }
  }

  ({String action, double t}) _voltPresentation(bool opponent) {
    if (!arena) {
      if (localAction == 'defeat' && localAge >= voltActionSeconds['defeat']!)
        return (action: 'defeat', t: 1.0);
      final duration = voltActionSeconds[localAction] ?? 1.1;
      if (localAge < duration && localAction.isNotEmpty)
        return (action: localAction, t: unit(localAge / duration));
      if (action == 'feed' && age < 1.7)
        return (action: 'feed', t: unit(age / 1.7));
      if (manualPosition && walkAge < walkDuration)
        return (action: 'move', t: unit(walkAge / walkDuration));
      final beat = clock % 23;
      if (!inspecting && !reduced && beat > 12 && beat < 13.7)
        return (action: 'inspect', t: (beat - 12) / 1.7);
      if (!inspecting && !reduced && beat > 18 && beat < 20.2)
        return (action: 'dance', t: (beat - 18) / 2.2);
      return (action: 'idle', t: 0.0);
    }
    if ({'victory', 'idle'}.contains(phase) &&
        {'win', 'loss'}.contains(data['result'])) {
      _voltOutcomeAt ??= clock;
      final won = data['result'] == 'win';
      final name = (opponent ? !won : won) ? 'victory' : 'defeat';
      return (
        action: name,
        t: unit((clock - _voltOutcomeAt!) / voltActionSeconds[name]!),
      );
    }
    if (opponent) {
      final name = data['enemyCombatAction'] as String? ?? 'attack';
      if (phase == 'enemy-flight' && data['stunned'] != true)
        return (
          action: data['intent'] == 'windup' ? 'charge' : name,
          t: unit(age / .72) * .9,
        );
      if (phase == 'reply' && data['stunned'] != true)
        return (action: name, t: .9 + .1 * unit(age / .25));
      return (action: 'idle', t: 0.0);
    }
    final name = phase.startsWith('counter-') ? 'attack' : combatAction;
    const releases = {
      'attack': .22,
      'quick': .26,
      'special': .46,
      'ultimate': .62,
      'pierce': .22,
      'burst': .26,
      'emp': .46,
    };
    final release = releases[name];
    final prepare =
        (data['prepareSeconds'] as num? ??
                (name == 'ultimate'
                    ? 0.72
                    : name == 'special'
                    ? 0.55
                    : name == 'quick'
                    ? 0.22
                    : 0.4))
            .toDouble();
    final impactSeconds = (data['impactSeconds'] as num? ?? .25).toDouble();
    if (release != null) {
      if (phase == 'approach')
        return (action: name, t: release * unit(age / prepare));
      if (phase == 'flight' || phase == 'counter-flight')
        return (action: name, t: release + (.9 - release) * progress);
      if (phase == 'impact' || phase == 'counter-hit')
        return (action: name, t: .9 + .1 * unit(age / impactSeconds));
    } else if ({'guard', 'dodge', 'charge'}.contains(name)) {
      if (phase == 'approach')
        return (action: name, t: .3 * unit(age / prepare));
      if (phase == 'impact')
        return (action: name, t: .3 + .1 * unit(age / impactSeconds));
      if (phase == 'enemy-flight')
        return (action: name, t: .4 + .4 * unit(age / .72));
      if (phase == 'reply') return (action: name, t: .8 + .2 * unit(age / .25));
    }
    return (action: 'idle', t: 0.0);
  }

  void _animateVolt(
    GameActor actor,
    GamePose old,
    _VoltPlayback playback,
    double dt, {
    required bool opponent,
  }) {
    final sample = _voltPresentation(opponent);
    final name = switch (sample.action) {
      'emp' => 'special',
      'pierce' => 'attack',
      'burst' => 'quick',
      _ => sample.action,
    };
    if (playback.action != sample.action) {
      playback.from = playback.action.isEmpty ? null : old;
      playback.fromFrame = playback.frame;
      playback.blendAt = clock;
      playback.cueT = -.001;
      playback.action = sample.action;
    }
    if (sample.t + .05 < playback.cueT) playback.cueT = -.001;
    final gear = (data['equipped'] as List? ?? const []).cast<String>();
    final displayed = opponent
        ? (data['enemyEquipped'] as List? ?? const []).cast<String>()
        : gear;
    final selected = opponent ? enemyWeapon : weapon;
    final mounted = displayed.isEmpty
        ? ''
        : displayed.contains(selected)
        ? selected
        : displayed.first;
    final pose = actor.pose;
    // Volt owns its articulated pose even during recovery and idle. The
    // generic weapon timeline can outlive his shorter electrical impulse.
    final rest = GamePose(clock)..headY += 32;
    final suspension = name == 'defeat' ? 1 - smooth(sample.t) : 1.0;
    rest.bodyY *= suspension;
    rest.headY = -85 + (rest.headY + 85) * suspension;
    rest.y -= (10 + 7 * math.sin(clock * 3 + (opponent ? 1 : 0))) * suspension;
    pose.blendFrom(rest, 0);
    pose.mode = 0;
    final rawFrame = applyVoltPose(
      pose,
      name,
      sample.t,
      equippedWeapon: mounted,
      clock: clock,
      guardImpact: !arena
          ? null
          : name == 'guard' &&
                phase == (opponent ? 'impact' : 'reply') &&
                data['stunned'] != true &&
                data['intent'] != 'windup'
          ? (0.35 +
                        ((data[opponent ? 'damage' : 'incoming'] as num? ?? 0) /
                            35))
                    .clamp(0.0, 1.0) *
                math.exp(-age * 12)
          : 0,
    );
    final blendSeconds = voltBlendSeconds(name);
    final blendWeight = reduced
        ? 1.0
        : unit((clock - playback.blendAt) / blendSeconds);
    final frame = blendVoltFrame(rawFrame, playback.fromFrame, blendWeight);
    if (mounted.isNotEmpty &&
        {'attack', 'quick', 'pierce', 'burst'}.contains(sample.action)) {
      pose.armR = -1.48 + .12 * math.sin(sample.t * math.pi * 6);
      pose.foreR = -.08;
      pose.deploy = smooth(sample.t / .15);
      pose.barrel = 18 - 9 * math.sin(sample.t * math.pi).abs();
    }
    pose.extra['voltPower'] = frame.coilGlow;
    pose.extra['voltCore'] = frame.coreGlow;
    pose.extra['voltFacePower'] = frame.power;
    pose.extra['voltAntenna'] = .08 * math.sin(clock * 3) + .1 * frame.charge;
    final travel = actor.motor.velocity.clamp(-100, 100) * .0015;
    pose.extra['joint8'] = pose.extra['joint8']! + travel;
    pose.extra['joint9'] = pose.extra['joint9']! - travel;
    if (!reduced && playback.from != null && blendWeight < 1)
      blendVoltPose(pose, playback.from!, blendWeight);
    if (!arena) voltTrackGaze(pose, gaze, weight: frame.power);
    for (final cue in voltCuesCrossed(name, playback.cueT, sample.t)) {
      if (data['sampleOnly'] == true) continue;
      final mountedShot =
          cue == 'volt_pulse' &&
          mounted.isNotEmpty &&
          {'attack', 'quick', 'pierce', 'burst'}.contains(sample.action) &&
          SceneAudio.cueSeconds.containsKey(mounted);
      audio.play(
        mountedShot ? mounted : cue,
        channel: opponent ? 'enemy:action' : 'player:action',
      );
    }
    playback.cueT = sample.t;
    playback.frame = frame;
  }

  Offset muzzle(GameActor a, String type) {
    final pose = a.pose;
    Offset rotate(Offset p, double r) => Offset(
      p.dx * math.cos(r) - p.dy * math.sin(r),
      p.dx * math.sin(r) + p.dy * math.cos(r),
    );
    final length = type == 'sniper'
        ? 195.0
        : type == 'fist'
        ? 89.0
        : 125.0;
    var point =
        const Offset(89, -48) +
        rotate(const Offset(0, 40), pose.armR) +
        rotate(Offset(0, length), pose.armR + pose.foreR);
    point = rotate(point, pose.rotation);
    return Offset(
      a.center + point.dx * scale * a.facing,
      floor + (-126 + pose.y + point.dy) * scale,
    );
  }

  Offset target(GameActor a) =>
      Offset(a.center, floor + (a.pose.y - 150) * scale);
  void camera(double value) {
    zoomTarget = value.clamp(1.0, 1.9);
    inspecting = zoomTarget > 1.05;
    if (!inspecting) pan = Offset.zero;
  }

  Offset worldPoint(Offset point) =>
      (point -
          Offset(
            viewport.width * (1 - zoom) / 2,
            viewport.height * (1 - zoom) / 2,
          ) -
          pan -
          shake) /
      zoom;

  void pointAt(Offset point) {
    if (arena) return;
    final world = worldPoint(point), pose = player.pose;
    final profile = robotProfiles[data['robot']] ?? robotProfiles['spark']!;
    final headX = (profile['headX'] as num? ?? 0).toDouble();
    final c = math.cos(pose.rotation), s = math.sin(pose.rotation);
    final head = Offset(
      player.center + (headX * c - pose.headY * s) * scale * player.facing,
      floor + (pose.y - 126 + headX * s + pose.headY * c) * scale,
    );
    final relative = Offset(
      (world.dx - head.dx) * player.facing,
      world.dy - head.dy,
    );
    final angle = pose.rotation + pose.head;
    gaze = Offset(
      ((relative.dx * math.cos(angle) + relative.dy * math.sin(angle)) /
              math.max(1, 12 * scale))
          .clamp(-12, 12),
      ((relative.dy * math.cos(angle) - relative.dx * math.sin(angle)) /
              math.max(1, 14 * scale))
          .clamp(-8, 8),
    );
  }

  bool robotAt(Offset point) => Rect.fromCenter(
    center: target(player),
    width: 240 * scale,
    height: 330 * scale,
  ).contains(worldPoint(point));

  void react() {
    _localSoundSerial++;
    tapBurst = clock - lastTap < .4 ? tapBurst + 1 : 1;
    lastTap = clock;
    final reactions =
        data['reactions'] as List? ?? ['joy', 'surprise', 'inspect'];
    final role = robotProfiles[data['robot']]?['class'];
    localAction = isVolt
        ? (tapBurst >= 3 ? 'anger' : _nextVoltReaction())
        : tapBurst >= 3
        ? (role == 'tank' || role == 'striker' ? 'anger' : 'dance')
        : reactions[reactionIndex++ % reactions.length] as String;
    if (isVolt) {
      _voltPlayer.from = player.pose;
      _voltPlayer.fromFrame = _voltPlayer.frame;
      _voltPlayer.action = localAction;
      _voltPlayer.blendAt = clock;
      _voltPlayer.cueT = -.001;
    }
    localAge = 0;
  }

  String _nextVoltReaction() {
    if (_reactionBag.isEmpty) {
      _reactionBag.addAll(
        ['joy', 'jump', 'surprise', 'inspect', 'playful', 'wave', 'dance']
          ..shuffle(_reactionRandom),
      );
      // The first greeting is friendly; subsequent reactions use a shuffle bag
      // with no repetitions until all seven have appeared.
      final wanted = reactionIndex == 0 ? 'joy' : null;
      if (wanted != null) {
        _reactionBag.remove(wanted);
        _reactionBag.insert(0, wanted);
      } else if (_reactionBag.first == localAction) {
        final first = _reactionBag.removeAt(0);
        _reactionBag.add(first);
      }
    }
    reactionIndex++;
    return _reactionBag.removeAt(0);
  }

  void moveTo(Offset point) {
    if (arena) return;
    _localSoundSerial++;
    final edge =
        (isVolt && (data['equipped'] as List? ?? const []).isEmpty
                ? 140
                : 210) *
            scale +
        8;
    final width = viewport.width;
    final x = worldPoint(point).dx.clamp(edge, math.max(edge, width - edge));
    walkFrom = player.center / width;
    walkTarget = x / width;
    walkDuration = ((x - player.center).abs() / math.max(1, 150 * scale)).clamp(
      .3,
      1.5,
    );
    walkAge = 0;
    manualPosition = true;
    player.facing = x < player.center ? -1 : 1;
    localAge = 99;
  }

  void showcase(String name) {
    if (arena || suspended || data['paused'] == true) return;
    _localSoundSerial++;
    localAction = name;
    localAge = 0;
    player.facing = 1;
    if (isVolt) {
      _voltPlayer.from = player.pose;
      _voltPlayer.fromFrame = _voltPlayer.frame;
      _voltPlayer.action = name;
      _voltPlayer.blendAt = clock;
      _voltPlayer.cueT = -.001;
      return; // Native Volt timeline owns its synchronised audio cues.
    }
  }

  @override
  void dispose() {
    audio.dispose();
    super.dispose();
  }
}

class _GameRig {
  _GameRig(rive.File file, this.board) {
    machine = board.stateMachine('RobotMotion')!;
    vm = file.createDefaultViewModelInstance(board)!;
    machine.bindViewModelInstance(vm);
    for (final name in [
      ...GamePose(0).values.keys,
      'mode',
      'wheelAngle',
      'lookX',
      'lookY',
      for (var i = 0; i < 16; i++) ...[
        'tread${i}X',
        'tread${i}Y',
        'tread${i}R',
      ],
    ]) {
      final field = vm.number(name);
      if (field == null) throw StateError('Missing game robot binding: $name');
      numbers[name] = field;
    }
    accent = vm.color('accent')!;
  }
  final rive.Artboard board;
  late final rive.StateMachine machine;
  late final rive.ViewModelInstance vm;
  late final rive.ViewModelInstanceColor accent;
  final numbers = <String, rive.ViewModelInstanceNumber>{};
  void advance(GameActor actor, double dt, Offset gaze, Color color) {
    for (final entry in actor.pose.values.entries) {
      numbers[entry.key]?.value = entry.value;
    }
    numbers['mode']!.value = actor.pose.shield > .1
        ? 3
        : actor.pose.mode == 0 && actor.motor.velocity.abs() > 1
        ? 1
        : actor.pose.mode.toDouble();
    numbers['lookX']!.value = gaze.dx;
    numbers['lookY']!.value = gaze.dy;
    numbers['wheelAngle']!.value = actor.motor.wheelAngle;
    for (var i = 0; i < 16; i++) {
      final tread = treadAt(i * trackLength / 16 + actor.motor.trackDistance);
      numbers['tread${i}X']!.value = tread.x;
      numbers['tread${i}Y']!.value = tread.y;
      numbers['tread${i}R']!.value = tread.rotation;
    }
    accent.value = color;
    machine.advanceAndApply(dt);
  }

  void dispose({bool ownBoard = false}) {
    machine.dispose();
    for (final field in numbers.values) {
      field.dispose();
    }
    accent.dispose();
    vm.dispose();
    if (ownBoard) board.dispose();
  }
}

Color robotColor(dynamic value) => Color(
  int.parse((value as String? ?? '#EFA74A').replaceFirst('#', 'FF'), radix: 16),
);

base class GameScenePainter extends rive.ArtboardPainter
    with rive.RiveTickerAwarePainterMixin {
  GameScenePainter(this.file);
  VoidCallback? onFirstPaint;
  final rive.File file;
  final scene = GameSceneClock();
  _GameRig? player, enemy;
  String enemyIdentity = '';
  bool resetTime = true, disposed = false;
  @override
  void artboardChanged(rive.Artboard artboard) {
    player?.dispose(ownBoard: true);
    enemy?.dispose(ownBoard: true);
    player = _GameRig(file, artboard);
    enemyIdentity = scene.data['enemy'] as String? ?? 'flora';
    enemy = scene.arena
        ? _GameRig(
            file,
            file.artboard(enemyIdentity == 'spark' ? 'Spark' : enemyIdentity) ??
                file.artboard('Spark')!,
          )
        : null;
  }

  @override
  bool advance(double elapsedSeconds) {
    if (disposed ||
        scene.suspended ||
        scene.hidden ||
        scene.data['paused'] == true)
      return false;
    final dt = resetTime || !elapsedSeconds.isFinite
        ? 0.0
        : math.max(0.0, elapsedSeconds);
    resetTime = false;
    final desired = scene.data['enemy'] as String? ?? 'flora';
    if (scene.arena && (enemy == null || desired != enemyIdentity)) {
      enemy?.dispose(ownBoard: true);
      enemyIdentity = desired;
      enemy = _GameRig(
        file,
        file.artboard(desired == 'spark' ? 'Spark' : desired) ??
            file.artboard('Spark')!,
      );
    }
    scene.advance(dt);
    if (!scene.isVolt)
      player?.advance(
        scene.player,
        dt,
        scene.gaze,
        scene.data['skin'] is String &&
                (scene.data['skin'] as String).startsWith('steel-')
            ? [
                const Color(0xFF65D4FF),
                const Color(0xFFA8AFF0),
                const Color(0xFFE8C77E),
                const Color(0xFF8CE3BC),
                const Color(0xFFF29CCB),
                const Color(0xFFE6F1FF),
              ][int.tryParse(
                    (scene.data['skin'] as String).split('-').last,
                  )?.clamp(0, 5) ??
                  0]
            : robotColor(scene.data['accent']),
      );
    if (scene.arena && scene.data['enemy'] != 'volt')
      enemy?.advance(
        scene.enemy,
        dt,
        Offset.zero,
        robotColor(scene.data['enemyAccent']),
      );
    return true;
  }

  @override
  void paint(rive.Renderer renderer, Size size, double paintPixelRatio) {
    if (disposed) return;
    scene.viewport = size;
    renderer.save();
    renderer.transform(
      rive.Mat2D.fromScaleAndTranslation(
        scene.zoom,
        scene.zoom,
        size.width * (1 - scene.zoom) / 2 + scene.pan.dx + scene.shake.dx,
        size.height * (1 - scene.zoom) / 2 + scene.pan.dy + scene.shake.dy,
      ),
    );
    void draw(
      _GameRig? rig,
      GameActor actor, {
      double opacity = 1,
      double shift = 0,
    }) {
      if (rig == null) return;
      final s = scene.scale, face = actor.facing;
      renderer.save();
      renderer.modulateOpacity(opacity);
      renderer.transform(
        rive.Mat2D.fromScaleAndTranslation(
          s * face,
          s,
          actor.center - (210 + actor.pose.x) * s * face + shift,
          scene.floor - 402 * s,
        ),
      );
      rig.board.draw(renderer);
      renderer.restore();
    }

    final illusion =
        scene.signatureVisible &&
        {'phantom', 'specter'}.contains(scene.signatureId);
    final illusionActor = scene.enemyShot ? scene.enemy : scene.player;
    final illusionRig = scene.enemyShot ? enemy : player;
    if (illusion) {
      for (final side in scene.ultimate ? [-1, 1] : [-1]) {
        draw(
          illusionRig,
          illusionActor,
          opacity: .32 * math.sin(scene.signatureT * math.pi),
          shift:
              side *
              (24 + 28 * math.sin(scene.signatureT * math.pi)) *
              scene.scale,
        );
      }
    }
    final disappearing =
        illusion &&
        scene.ultimate &&
        scene.signatureT > .3 &&
        scene.signatureT < .68;
    if (!scene.isVolt)
      draw(
        player,
        scene.player,
        opacity: disappearing && !scene.enemyShot ? .13 : 1,
      );
    if (scene.arena && scene.data['enemy'] != 'volt')
      draw(
        enemy,
        scene.enemy,
        opacity: disappearing && scene.enemyShot ? .13 : 1,
      );
    renderer.restore();
    if (player != null &&
        (!scene.arena || enemy != null) &&
        onFirstPaint != null) {
      final callback = onFirstPaint;
      onFirstPaint = null;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!disposed) callback?.call();
      });
    }
  }

  @override
  void dispose() {
    if (disposed) return;
    disposed = true;
    player?.dispose(ownBoard: true);
    enemy?.dispose(ownBoard: true);
    scene.dispose();
    super.dispose();
  }
}

class GameSceneView extends StatefulWidget {
  const GameSceneView({
    super.key,
    this.file,
    this.painter,
    this.nativeScene,
    this.onRobotTap,
    this.onFirstPaint,
  }) : assert(nativeScene != null || (file != null && painter != null));
  final rive.File? file;
  final GameScenePainter? painter;
  final GameSceneClock? nativeScene;
  final VoidCallback? onRobotTap;
  final VoidCallback? onFirstPaint;
  @override
  State<GameSceneView> createState() => _GameSceneViewState();
}

class _GameSceneViewState extends State<GameSceneView> {
  double startZoom = 1;
  GameSceneClock get scene => widget.nativeScene ?? widget.painter!.scene;
  @override
  Widget build(BuildContext context) => RepaintBoundary(
    child: MouseRegion(
      onHover: (e) => scene.pointAt(e.localPosition),
      onExit: (_) => scene.gaze = Offset.zero,
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: (_) => scene.audio.unlock(),
        onPointerMove: (e) => scene.pointAt(e.localPosition),
        onPointerSignal: (e) {
          if (e is PointerScrollEvent &&
              (scene.expanded || scene.demonstration))
            scene.camera(scene.zoomTarget - e.scrollDelta.dy * .0015);
        },
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapUp: scene.arena
              ? null
              : (e) {
                  scene.pointAt(e.localPosition);
                  if (scene.robotAt(e.localPosition)) {
                    scene.react();
                    if (!scene.demonstration) widget.onRobotTap?.call();
                  } else {
                    scene.moveTo(e.localPosition);
                  }
                },
          onLongPress: scene.arena ? null : () => scene.showcase('ultimate'),
          onScaleStart: scene.expanded || scene.demonstration
              ? (_) {
                  startZoom = scene.zoomTarget;
                }
              : null,
          onScaleUpdate: scene.expanded || scene.demonstration
              ? (e) {
                  if (e.pointerCount > 1)
                    scene.camera(startZoom * e.scale);
                  else if (scene.inspecting)
                    scene.pan = Offset(
                      (scene.pan.dx + e.focalPointDelta.dx).clamp(
                        -100.0,
                        100.0,
                      ),
                      (scene.pan.dy + e.focalPointDelta.dy).clamp(-70.0, 70.0),
                    );
                }
              : null,
          child: Stack(
            fit: StackFit.expand,
            children: [
              if (widget.nativeScene == null)
                rive.RiveFileWidget(
                  file: widget.file!,
                  painter: widget.painter!,
                  artboardName: scene.data['robot'] == 'spark'
                      ? 'Spark'
                      : scene.data['robot'] as String?,
                ),
              IgnorePointer(
                child: CustomPaint(
                  painter: widget.nativeScene == null
                      ? GameEffectsPainter(scene)
                      : _NativeVoltEffectsPainter(scene, () {
                          if (mounted) widget.onFirstPaint?.call();
                        }),
                ),
              ),
              if ((scene.expanded || scene.demonstration) && !scene.arena)
                Positioned(
                  top: scene.arena ? 78 : 46,
                  right: 12,
                  child: Column(
                    children: [
                      IconButton.filledTonal(
                        tooltip: 'Осмотреть робота',
                        iconSize: 20,
                        onPressed: () => setState(
                          () => scene.camera(scene.inspecting ? 1 : 1.6),
                        ),
                        icon: const Icon(Icons.zoom_in),
                      ),
                      IconButton.filledTonal(
                        tooltip: 'Сбросить камеру',
                        iconSize: 20,
                        onPressed: () => setState(() => scene.camera(1)),
                        icon: const Icon(Icons.center_focus_strong),
                      ),
                    ],
                  ),
                ),
              Positioned(
                left: 8,
                bottom: scene.arena ? 42 : 49,
                child: IconButton(
                  tooltip: 'Звук анимаций',
                  constraints: const BoxConstraints(
                    minWidth: 48,
                    minHeight: 48,
                  ),
                  onPressed: () => setState(() {
                    scene.audio.muted = !scene.audio.muted;
                    if (scene.audio.muted) scene.audio.pause();
                  }),
                  icon: Icon(
                    scene.audio.muted
                        ? Icons.volume_off_rounded
                        : Icons.volume_up_rounded,
                    size: 19,
                    color: const Color(0xFFAFE4F4),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _NativeVoltEffectsPainter extends GameEffectsPainter {
  _NativeVoltEffectsPainter(super.scene, this.onFirstPaint);
  final VoidCallback onFirstPaint;
  bool reported = false;
  @override
  void paint(Canvas canvas, Size size) {
    super.paint(canvas, size);
    if (!reported &&
        size.width > 0 &&
        size.height > 0 &&
        scene.playerVoltFrame != null &&
        !scene.hidden &&
        !scene.suspended) {
      reported = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => onFirstPaint());
    }
  }
}

class GameEffectsPainter extends CustomPainter {
  GameEffectsPainter(this.scene) : super(repaint: scene);
  final GameSceneClock scene;
  @override
  void paint(Canvas canvas, Size size) {
    final s = scene.scale;
    canvas.save();
    canvas.translate(
      size.width * (1 - scene.zoom) / 2 + scene.pan.dx + scene.shake.dx,
      size.height * (1 - scene.zoom) / 2 + scene.pan.dy + scene.shake.dy,
    );
    canvas.scale(scene.zoom);
    final paint = Paint()..strokeCap = StrokeCap.round;
    void glow(Offset p, double radius, Color color) {
      if (radius <= .01) return;
      canvas.drawCircle(
        p,
        radius * 2.4,
        Paint()
          ..shader = RadialGradient(
            colors: [color.withValues(alpha: .65), color.withValues(alpha: 0)],
          ).createShader(Rect.fromCircle(center: p, radius: radius * 2.4)),
      );
      canvas.drawCircle(
        p,
        radius * .45,
        paint
          ..color = Colors.white
          ..style = PaintingStyle.fill,
      );
    }

    void shield(GameActor a) {
      if (a.pose.shield < .05) return;
      final rect = Rect.fromCenter(
        center: scene.target(a) + Offset(40 * s * a.facing, -10 * s),
        width: 120 * s,
        height: 255 * s,
      );
      canvas.drawOval(
        rect,
        Paint()
          ..shader = RadialGradient(
            colors: [
              const Color(0x005DE7FF),
              Color.fromRGBO(80, 220, 255, .24 * a.pose.shield),
            ],
          ).createShader(rect),
      );
      canvas.drawOval(
        rect,
        paint
          ..color = const Color(0xFF95F5FF).withValues(alpha: a.pose.shield)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3,
      );
      for (var i = 0; i < 6; i++) {
        final y = rect.top + rect.height * (i + .5) / 6;
        canvas.drawLine(
          Offset(rect.left + 12, y),
          Offset(rect.right - 12, y),
          paint
            ..color = const Color(0x5CAAF9FF)
            ..strokeWidth = 1,
        );
      }
    }

    if (!scene.arena && !scene.reduced) {
      final workshopLevel = (scene.data['workshopLevel'] as num? ?? 0).toInt();
      final inventions = scene.data['inventions'] as Map? ?? const {};
      final beam = Path()
        ..moveTo(size.width * .77, 0)
        ..lineTo(size.width * .35, size.height * .88)
        ..lineTo(size.width * .94, size.height * .88)
        ..close();
      canvas.drawPath(
        beam,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0x24FFE8AD), Color(0x00FFE8AD)],
          ).createShader(Offset.zero & size),
      );
      for (var i = 0; i < 14; i++) {
        final x =
            (i * .143 * size.width + math.sin(scene.clock * .4 + i) * 20) %
            size.width;
        final y = (size.height * (i * .117) + scene.clock * 5) % size.height;
        canvas.drawCircle(
          Offset(x, y),
          i.isEven ? 1.3 : .7,
          paint
            ..color = const Color(0x70FFF1C1)
            ..style = PaintingStyle.fill,
        );
      }
      for (var i = 0; i < 2 + workshopLevel.clamp(0, 3); i++) {
        canvas.save();
        canvas.translate(
          size.width * (i.isEven ? .08 : .92),
          size.height * (.74 - (i ~/ 2) * .18),
        );
        canvas.rotate(scene.clock * (i == 0 ? .5 : -.4));
        for (var tooth = 0; tooth < 8; tooth++) {
          canvas.save();
          canvas.rotate(tooth * math.pi / 4);
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              const Rect.fromLTWH(-2, -15, 4, 8),
              const Radius.circular(1),
            ),
            paint
              ..color = const Color(0x88D6B577)
              ..style = PaintingStyle.fill,
          );
          canvas.restore();
        }
        canvas.drawCircle(
          Offset.zero,
          10,
          paint
            ..color = const Color(0x99B39C70)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3,
        );
        canvas.drawCircle(
          Offset.zero,
          3,
          paint
            ..color = const Color(0x99EDF7F8)
            ..style = PaintingStyle.fill,
        );
        canvas.restore();
      }
      // Upgrades add real moving machinery, not only a different title/color.
      if (workshopLevel >= 2) {
        for (final side in [-1, 1]) {
          final point = Offset(
            size.width * (side < 0 ? .09 : .91),
            size.height * .2,
          );
          canvas.save();
          canvas.translate(point.dx, point.dy);
          canvas.drawCircle(
            Offset.zero,
            17,
            paint
              ..color = const Color(0x99436786)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 3,
          );
          canvas.rotate(scene.clock * (side < 0 ? 4 : -4));
          for (var blade = 0; blade < 4; blade++) {
            canvas.rotate(math.pi / 2);
            canvas.drawOval(
              const Rect.fromLTWH(-3, 2, 6, 13),
              paint
                ..style = PaintingStyle.fill
                ..color = const Color(0xB886D6EF),
            );
          }
          canvas.restore();
        }
      }
      if (workshopLevel >= 3) {
        final rect = Rect.fromCenter(
          center: Offset(size.width * .5, size.height * .9),
          width: size.width * .76,
          height: 16,
        );
        canvas.drawOval(
          rect,
          paint
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2
            ..color = Color.fromRGBO(
              76,
              223,
              255,
              .35 + .2 * math.sin(scene.clock * 2),
            ),
        );
      }
      if ((inventions['lamp'] as num? ?? 0) > 0) {
        final p = Offset(size.width * .12, size.height * .65);
        glow(p, 5 + math.sin(scene.clock * 2), const Color(0xFFFFD37D));
      }
    }

    void drawVolt(GameActor actor, VoltFrame? frame, bool opponent) {
      if (frame == null) return;
      final origin = Offset(
        actor.center,
        scene.floor + (actor.pose.y - 126) * s,
      );
      paintVoltMotionEchoes(
        canvas,
        frame,
        origin,
        s,
        facing: actor.facing,
        reduced: scene.reduced,
      );
      drawVoltModel(
        canvas,
        actor.pose,
        origin,
        s,
        actor.facing,
        gaze: opponent ? Offset.zero : scene.gaze,
      );
      paintVoltEffects(
        canvas,
        frame,
        voltAnchors(actor.pose, origin, s, facing: actor.facing),
        scene.arena
            ? scene.target(opponent ? scene.player : scene.enemy)
            : Offset(size.width * .87, scene.floor - 130 * s),
        scene.floor,
        s,
        reduced: scene.reduced,
        facing: actor.facing,
        preview: !scene.arena,
      );
    }

    if (scene.isVolt) drawVolt(scene.player, scene.playerVoltFrame, false);
    if (scene.arena && scene.data['enemy'] == 'volt')
      drawVolt(scene.enemy, scene.enemyVoltFrame, true);
    shield(scene.player);
    if (scene.arena) shield(scene.enemy);
    final dummy = Offset(size.width * .87, scene.floor - 130 * s);
    if (!scene.arena &&
        (scene.demonstration ||
            scene.localAge < 2.25 &&
                {
                  'attack',
                  'special',
                  'ultimate',
                }.contains(scene.localAction))) {
      for (final radius in [32.0, 21.0, 9.0]) {
        canvas.drawCircle(
          dummy,
          radius * s,
          paint
            ..color = const Color(0xAA8BEDFF)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2 * s,
        );
      }
      canvas.drawLine(
        dummy + Offset(0, 32 * s),
        Offset(dummy.dx, scene.floor),
        paint
          ..color = const Color(0xCC88A6BC)
          ..strokeWidth = 4 * s,
      );
      canvas.drawOval(
        Rect.fromCenter(
          center: Offset(dummy.dx, scene.floor),
          width: 55 * s,
          height: 12 * s,
        ),
        paint
          ..color = const Color(0x6674E8FF)
          ..style = PaintingStyle.fill,
      );
    }
    if (scene.signatureVisible && scene.signatureId != 'volt') {
      final actor = scene.enemyShot ? scene.enemy : scene.player;
      final defender = scene.enemyShot ? scene.player : scene.enemy;
      final origin =
          scene.target(actor) + Offset(35 * s * actor.facing, -8 * s);
      var aim = scene.arena ? scene.target(defender) : dummy;
      canvas.save();
      if (actor.facing < 0) {
        canvas.translate(origin.dx * 2, 0);
        canvas.scale(-1, 1);
        aim = Offset(origin.dx * 2 - aim.dx, aim.dy);
      }
      paintSignature(
        canvas,
        scene.signatureId,
        origin,
        aim,
        scene.floor,
        s,
        scene.signatureT,
        robotColor(scene.data[scene.enemyShot ? 'enemyAccent' : 'accent']),
        ultimate: scene.ultimate,
        reduced: scene.reduced,
      );
      canvas.restore();
    }
    if (scene.arena && scene.phase == 'approach' && scene.weapon == 'sniper') {
      final start = scene.muzzle(scene.player, 'sniper'),
          end = scene.target(scene.enemy);
      canvas.drawLine(
        start,
        end,
        paint
          ..color = const Color(0xAAFF546F)
          ..strokeWidth = 1
          ..style = PaintingStyle.stroke,
      );
      canvas.drawCircle(
        end,
        9 + 3 * math.sin(scene.age * 12),
        paint..strokeWidth = 1.5,
      );
      canvas.drawLine(
        end + const Offset(-16, 0),
        end + const Offset(16, 0),
        paint,
      );
      canvas.drawLine(
        end + const Offset(0, -16),
        end + const Offset(0, 16),
        paint,
      );
    }
    final voltBuiltin =
        scene.data[scene.enemyShot ? 'enemy' : 'robot'] == 'volt' &&
        ((scene.data[scene.enemyShot ? 'enemyEquipped' : 'equipped'] as List? ??
                    const [])
                .isEmpty ||
            {'special', 'ultimate'}.contains(scene.activeCombatAction));
    if (scene.visibleShot && !scene.signatureVisible && !voltBuiltin) {
      final actor = scene.enemyShot ? scene.enemy : scene.player;
      final defender = scene.enemyShot ? scene.player : scene.enemy;
      final type = scene.activeWeapon, t = scene.progress;
      final from = scene.muzzle(actor, type),
          to = scene.arena ? scene.target(defender) : dummy;
      if (scene.activeCombatAction == 'emp') {
        for (var i = 0; i < 3; i++) {
          canvas.drawCircle(
            from,
            (18 +
                    unit(t * 1.5 - i * .18) *
                        (to - from).distance /
                        math.max(.01, s)) *
                s,
            paint
              ..color = const Color(0x9977BFFF)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 3 * s,
          );
        }
      }
      if (scene.activeCombatAction == 'pierce') {
        canvas.drawLine(
          from,
          Offset.lerp(from, to, unit(t * 2))!,
          paint
            ..color = const Color(0xCCFFF1C9)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2 * s,
        );
      }
      if (scene.activeCombatAction == 'burst') {
        for (var i = 0; i < 3; i++) {
          final point = Offset.lerp(from, to, unit(t * 1.7 - i * .22))!;
          glow(point, 6 * s, const Color(0xFFFFD082));
        }
      }
      final color = type == 'rocket'
          ? const Color(0xFFFFAE58)
          : type == 'sniper'
          ? const Color(0xFFFF6D9F)
          : const Color(0xFF76EEFF);
      if (type == 'sword') {
        final reach = (to - from).distance;
        final rect = Rect.fromCircle(
          center: from,
          radius: math.max(20, reach * .4),
        );
        canvas.drawArc(
          rect,
          -1.6 + 2 * t,
          1.8,
          false,
          paint
            ..color = const Color(0x996BFFF0)
            ..strokeWidth = 16 * s
            ..style = PaintingStyle.stroke,
        );
        canvas.drawArc(
          rect,
          -1.6 + 2 * t,
          1.8,
          false,
          paint
            ..color = Colors.white
            ..strokeWidth = 3 * s,
        );
      } else if ({'laser', 'repair', 'ion'}.contains(type)) {
        final beam = Offset.lerp(from, to, math.min(1, t * 3))!;
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = (type == 'repair'
                ? const Color(0x447AFFBE)
                : type == 'ion'
                ? const Color(0x448EA5FF)
                : const Color(0x44FF6BAD))
            ..style = PaintingStyle.stroke
            ..strokeWidth = 22 * s,
        );
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = (type == 'repair'
                ? const Color(0xFF86FFD3)
                : type == 'ion'
                ? const Color(0xFFBBA6FF)
                : const Color(0xFFFF8DBE))
            ..strokeWidth = 6 * s,
        );
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = Colors.white
            ..strokeWidth = 2 * s,
        );
      } else if ({'electric', 'magnetic', 'emp'}.contains(type)) {
        final end = Offset.lerp(from, to, t)!;
        final path = Path()..moveTo(from.dx, from.dy);
        for (var j = 1; j <= 14; j++) {
          final p = Offset.lerp(from, end, j / 14)!;
          path.lineTo(
            p.dx,
            p.dy + (j == 14 ? 0 : math.sin(j * 2 + scene.clock * 50) * 15 * s),
          );
        }
        canvas.drawPath(
          path,
          paint
            ..color = const Color(0x665DE7FF)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 12 * s,
        );
        canvas.drawPath(
          path,
          paint
            ..color = const Color(0xFFE2FFFF)
            ..strokeWidth = 3 * s,
        );
        if (type != 'electric') {
          canvas.drawCircle(
            end,
            (12 + 26 * t) * s,
            paint
              ..color = const Color(0xBBAE92FF)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 3 * s,
          );
          canvas.drawCircle(
            end,
            (5 + 13 * t) * s,
            paint
              ..color = const Color(0xDDDEBAFF)
              ..strokeWidth = 2 * s,
          );
        }
      } else if (type == 'flame' || type == 'cryo') {
        final end = Offset.lerp(from, to, t)!;
        for (var j = 0; j < 24; j++) {
          final along = ((scene.clock * 4 + j / 24) % 1);
          final center =
              Offset.lerp(from, end, along)! +
              Offset(0, math.sin(j * 7 + scene.clock * 22) * 16 * s * along);
          final radius = (6 + 18 * along) * s;
          canvas.drawCircle(
            center,
            radius,
            paint
              ..color = Color.lerp(
                type == 'cryo'
                    ? const Color(0xDDE8FFFF)
                    : const Color(0xDDFFF7BD),
                type == 'cryo'
                    ? const Color(0x7785CEFF)
                    : const Color(0x77F46B48),
                along,
              )!
              ..style = PaintingStyle.fill,
          );
        }
      } else if (type == 'machinegun' || type == 'blaster') {
        for (var j = 0; j < 4; j++) {
          final f = unit(t * 1.4 - j * .12);
          final point = Offset.lerp(from, to, f)!;
          canvas.drawLine(
            point - Offset(18 * s * actor.facing, 0),
            point,
            paint
              ..color = const Color(0xFFFFD57F)
              ..strokeWidth = 4 * s
              ..style = PaintingStyle.stroke,
          );
        }
        if ((scene.age * 16) % 1 < .5)
          glow(from, 18 * s, const Color(0xFFFFD082));
      } else if (type == 'drone') {
        final drone =
            Offset.lerp(from, to, t * .7)! +
            Offset(0, -40 * s * math.sin(t * math.pi));
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromCenter(center: drone, width: 35 * s, height: 21 * s),
            Radius.circular(7 * s),
          ),
          paint
            ..color = const Color(0xFFC2B5EE)
            ..style = PaintingStyle.fill,
        );
        for (final side in [-1, 1]) {
          canvas.drawLine(
            drone +
                Offset(
                  side * 20 * s - 12 * s,
                  math.sin(scene.clock * 50) * 4 * s,
                ),
            drone + Offset(side * 20 * s + 12 * s, 0),
            paint
              ..color = const Color(0xAA99E7F4)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 3 * s,
          );
        }
        final shot = Offset.lerp(drone, to, unit((t - .35) * 2))!;
        glow(shot, 8 * s, const Color(0xFFB8A4FF));
      } else if (type == 'disc' || type == 'grenade') {
        final position =
            Offset.lerp(from, to, t)! +
            Offset(0, type == 'grenade' ? -math.sin(t * math.pi) * 60 * s : 0);
        canvas.save();
        canvas.translate(position.dx, position.dy);
        canvas.rotate(scene.clock * 30);
        canvas.drawOval(
          Rect.fromCenter(
            center: Offset.zero,
            width: 34 * s,
            height: (type == 'disc' ? 9 : 28) * s,
          ),
          paint
            ..style = PaintingStyle.fill
            ..color = const Color(0xFFBBD9EC),
        );
        canvas.drawCircle(Offset.zero, 5 * s, paint..color = color);
        canvas.restore();
        glow(position, 7 * s, color);
      } else if (type == 'fist' || type == 'drill') {
        for (var i = 0; i < 6; i++) {
          final path = Path()..moveTo(from.dx - 30 * s, from.dy);
          for (var j = 0; j < 7; j++) {
            path.lineTo(
              from.dx + j * 7 * s,
              from.dy + math.sin(scene.clock * 47 + j * 2 + i) * 18 * s,
            );
          }
          canvas.drawPath(
            path,
            paint
              ..color = color
              ..style = PaintingStyle.stroke
              ..strokeWidth = 2,
          );
        }
        if (t > .55) glow(from, 24 * s, color);
      } else {
        final position = Offset.lerp(from, to, t)!;
        if (type == 'rocket') {
          for (var missile = 0; missile < 2; missile++) {
            final p =
                position +
                Offset(
                  0,
                  (missile == 0 ? -12 : 12) * s +
                      math.sin(t * math.pi) * -50 * s,
                );
            final tail = Offset.lerp(from, p, .75)!;
            canvas.drawLine(
              tail,
              p,
              paint
                ..color = const Color(0x66B7C9D9)
                ..strokeWidth = 13 * s
                ..style = PaintingStyle.stroke,
            );
            canvas.drawLine(
              p - Offset(26 * s * actor.facing, 0),
              p,
              paint
                ..color = const Color(0xFFFFD48B)
                ..strokeWidth = 9 * s,
            );
            canvas.drawRRect(
              RRect.fromRectAndRadius(
                Rect.fromCenter(center: p, width: 30 * s, height: 13 * s),
                Radius.circular(5 * s),
              ),
              paint
                ..color = const Color(0xFFE9F2FF)
                ..style = PaintingStyle.fill,
            );
            glow(p - Offset(18 * s * actor.facing, 0), 9 * s, color);
          }
        } else {
          final tail = Offset.lerp(
            from,
            position,
            type == 'sniper' ? .4 : .75,
          )!;
          canvas.drawLine(
            tail,
            position,
            paint
              ..color = color.withValues(alpha: .22)
              ..strokeWidth = (type == 'sniper' ? 13 : 24) * s
              ..style = PaintingStyle.stroke,
          );
          canvas.drawLine(
            tail,
            position,
            paint
              ..color = color
              ..strokeWidth = (type == 'sniper' ? 3 : 9) * s,
          );
          glow(position, (type == 'sniper' ? 9 : 17) * s, color);
        }
      }
      if (scene.age < .16) glow(from, (1 - scene.age / .16) * 43 * s, color);
    }
    if (scene.impact > .01) {
      final point = scene.target(
        scene.phase == 'reply' ? scene.player : scene.enemy,
      );
      final age = scene.age;
      glow(point, (26 + age * 75) * s * scene.impact, const Color(0xFFFFE3A1));
      canvas.drawCircle(
        point,
        (30 + age * 150) * s,
        paint
          ..color = const Color(0xFFFFD28C).withValues(alpha: scene.impact)
          ..strokeWidth = 4 * scene.impact
          ..style = PaintingStyle.stroke,
      );
      for (var i = 0; i < 8; i++) {
        final a = i * math.pi / 4 + .1;
        final v = Offset(math.cos(a), math.sin(a));
        canvas.drawLine(
          point + v * (20 + age * 90) * s,
          point + v * (55 + age * 160) * s,
          paint..strokeWidth = 3 * scene.impact,
        );
      }
    }
    for (final p in scene.effects.particles) {
      final opacity = 1 - unit(p.age / p.life);
      paint
        ..color = p.color.withValues(alpha: opacity * (p.smoke ? .4 : 1))
        ..style = PaintingStyle.fill;
      if (p.smoke)
        canvas.drawCircle(p.position, p.radius * (1 + p.age * 2), paint);
      else
        canvas.drawLine(
          p.position,
          p.position - p.velocity * .025,
          paint..strokeWidth = p.radius,
        );
    }
    if (!scene.arena && scene.action == 'feed' && scene.age < 1.3) {
      final t = unit(scene.age / 1.3), center = scene.target(scene.player);
      for (var i = 0; i < 4; i++) {
        final p =
            center +
            Offset(math.sin(i * 2.4 + t * 4) * 50 * s, (60 - 130 * t) * s);
        canvas.drawCircle(
          p,
          5 * s,
          paint
            ..color = const Color(0xFFFDD886)
            ..style = PaintingStyle.fill,
        );
        canvas.drawCircle(
          p,
          8 * s,
          paint
            ..color = const Color(0x66FFF4D5)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2,
        );
      }
      glow(center, 25 * s * pulse(t, 0, 1), const Color(0xFF91FFE1));
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(GameEffectsPainter oldDelegate) =>
      oldDelegate.scene != scene;
}
