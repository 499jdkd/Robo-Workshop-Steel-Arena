import 'dart:convert';
import 'dart:math' as math;

import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:rive/rive.dart' as rive;

import 'robot/game_motion.dart';
import 'robot/motion_model.dart';
import 'robot/scene_audio.dart';
import 'robot/robot_profiles.dart';
import 'robot/rig_cache.dart';

/// Semantic Flet events drive native timelines, without Python frame updates.
class GameRiveControl extends StatefulWidget {
  const GameRiveControl({super.key, required this.control});
  final Control control;
  @override
  State<GameRiveControl> createState() => _GameRiveControlState();
}

class _GameRiveControlState extends State<GameRiveControl>
    with WidgetsBindingObserver {
  rive.File? file;
  Future<rive.File?>? loading;
  GameScenePainter? painter;
  RigLease? lease;
  String source = '', renderer = '';
  int generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  void load() {
    final src = widget.control.getString('src', '')!;
    final requested = widget.control.getString('renderer', 'auto')!;
    // Both factories use the same native Rive artboard/state machine. The
    // Flutter compositor avoids the platform-texture path on Android/iOS.
    final engine = requested == 'auto'
        ? (!kIsWeb && {TargetPlatform.android, TargetPlatform.iOS}.contains(defaultTargetPlatform)
            ? 'flutter' : 'rive')
        : requested;
    if (src == source && engine == renderer) return;
    source = src;
    renderer = engine;
    final current = ++generation;
    painter?.dispose();
    painter = null;
    final previous = lease;
    file = null;
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.release());
    final asset = widget.control.backend.getAssetSource(src);
    final factory = engine == 'flutter'
        ? rive.Factory.flutter
        : rive.Factory.rive;
    lease=acquireRig('${asset.path}|$engine',()=>rive.RiveNative.init().then((_) =>
        (asset.isFile
                ? rive.File.path(asset.path, riveFactory: factory)
                : rive.File.url(asset.path, riveFactory: factory))));
    loading = lease!.future
            .then((value) {
              if (!mounted || current != generation) {
                return null;
              }
              return file = value;
            });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    painter?.scene.suspended = state != AppLifecycleState.resumed;
    painter?.scene.audio.pause();
    painter?.resetTime = true;
    if (state == AppLifecycleState.resumed) painter?.scheduleRepaint();
  }

  @override
  void didHaveMemoryPressure(){clearIdleRigCache();}

  @override
  Widget build(BuildContext context) {
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
          if (value == null) return const Center(child:SizedBox(width:25,height:25,child:CircularProgressIndicator(strokeWidth:2,color:Color(0xFF87DEFF))));
          final p = painter ??= GameScenePainter(value);
          final data =
              jsonDecode(widget.control.getString('payload', '{}')!)
                  as Map<String, dynamic>;
          p.scene.reduced = MediaQuery.disableAnimationsOf(context);
          p.scene.update(data);
          if (data['sound'] != false)
            p.scene.audio.configure(widget.control.backend);
        return LayoutBuilder(builder:(context,constraints) {
          p.scene.viewport=constraints.biggest;
          return GameSceneView(file:value,painter:p);
        });
        },
      ),
    );
  }

  @override
  void dispose() {
    generation++;
    WidgetsBinding.instance.removeObserver(this);
    painter?.dispose();
    final previous=lease;
    WidgetsBinding.instance.addPostFrameCallback((_)=>previous?.release());
    super.dispose();
  }
}

class GameSceneClock extends ChangeNotifier {
  Map<String, dynamic> data = {};
  final player = GameActor(), enemy = GameActor()..facing = -1;
  final effects = GameEffects();
  void Function()? pendingBurst;
  GamePose? previousPlayer, previousEnemy;
  final audio = SceneAudio();
  Size viewport = const Size(390, 294);
  double clock = 0, age = 0, zoom = 1, zoomTarget = 1, patrol = 0;
  Offset pan = Offset.zero, gaze = Offset.zero;
  bool reduced = false, suspended = false, inspecting = false;
  bool get arena => data['arena'] == true;
  bool get expanded => data['expanded'] == true;
  String get phase => data['phase'] as String? ?? 'idle';
  String get action => data['action'] as String? ?? 'idle';
  String get weapon => data['weapon'] as String? ?? 'plasma';
  String get enemyWeapon => data['enemyWeapon'] as String? ?? 'plasma';
  double get scale => math.min(
    viewport.height * (arena ? .64 : .76) / 330,
    // Reserve the complete 420px artboard, including deployed long weapons,
    // instead of fitting only the 240px chassis and cropping its extremities.
    viewport.width * (arena ? .46 : .90) / 420,
  );
  double get floor => viewport.height * (arena ? .84 : .86);
  bool get playerShot =>
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
  double get progress => unit(age / (phase == 'counter-flight' ? .65 : .95));
  double get impact =>
      ((phase == 'impact' && (data['damage'] as num? ?? 0) > 0) ||
          (phase == 'reply' && (data['incoming'] as num? ?? 0) > 0) ||
          phase == 'counter-hit')
      ? math.exp(-age * 7)
      : 0;
  Offset get shake => reduced
      ? Offset.zero
      : Offset(
          math.sin(age * 103) * 9 * impact,
          math.cos(age * 137) * 5 * impact,
        );

  void update(Map<String, dynamic> next) {
    if(next['robot']!=data['robot'] || next['arena']!=data['arena']) {
      patrol=0;zoom=zoomTarget=1;pan=Offset.zero;gaze=Offset.zero;
      inspecting=false;player.facing=1;effects.particles.clear();
    }
    final changed = next['event'] != data['event'];
    final previousAction = action;
    final keepFeeding =
        !arena &&
        previousAction == 'feed' &&
        age < 1.4 &&
        next['action'] == 'joy';
    final keepReaction = !arena && previousAction == next['action'] && age < .5;
    data = next;
    if (keepFeeding) data['action'] = 'feed';
    audio.enabled = next['sound'] != false;
    player.mobility = next['mobility'] as String? ?? 'tracks';
    enemy.mobility = next['enemyMobility'] as String? ?? 'tracks';
    if (!changed || keepFeeding || keepReaction) return;
    previousPlayer = player.pose;
    previousEnemy = enemy.pose;
    age = 0;
    if (arena) {
      if (phase == 'approach')
        audio.play(weapon == 'sniper' ? 'aim' : 'deploy');
      if (visibleShot)
        audio.play(activeWeapon == 'fist' ? 'electric' : activeWeapon);
      if (phase == 'impact' || phase == 'reply' || phase == 'counter-hit') {
        final guarded = phase == 'reply' && action == 'guard';
        final damage =
            next[phase == 'reply' ? 'incoming' : 'damage'] as num? ?? 0;
        if (damage > 0 || guarded) {
          audio.play(guarded ? 'shield' : 'impact');
          final target = phase == 'reply' ? player : enemy;
          if (!reduced) {
            pendingBurst=() {
            final point=Offset(target.center,floor-140*scale);
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
      if (phase == 'victory') audio.play('victory');
    } else if (action == 'feed') {
      audio.play('feed');
      if (!reduced) pendingBurst=()=>effects.burst(
          Offset(player.center, floor - 190 * scale),
          const Color(0xFF6FEAD2),
          count: 14,
        );
    }
  }

  void advance(double dt) {
    if (suspended || data['paused'] == true) return;
    clock += dt;
    age += dt;
    effects.advance(dt);
    final s = scale;
    player.pose = GamePose(clock);
    enemy.pose = GamePose(clock + .7);
    double px = viewport.width * (arena ? .23 : .5), ex = viewport.width * .77;
    final p = player.pose, e = enemy.pose;
    if (!arena) {
      final reacting = age < (action == 'feed' ? 1.7 : .95) && action != 'idle';
      final id = data['robot'];
      final speed = id == 'forge' || id == 'aegis'
          ? .64
          : id == 'volt' || id == 'glacier'
          ? 1.45
          : 1.0;
      if (!inspecting && !reduced && !reacting) patrol += dt * speed;
      final span = math.max(
        0,
        (viewport.width - 230 * s) * (expanded ? .36 : .22),
      );
      px += span * math.sin(patrol * .72);
      if (!inspecting && !reacting && !reduced)
        player.facing = math.cos(patrol * .72) < 0 ? -1 : 1;
      if (reacting) p.emotion(action, age);
      if (!reacting && !inspecting && !reduced) {
        final beat = clock % 23;
        if (beat > 12 && beat < 13.3) p.emotion('surprise', beat - 12);
        if (beat > 19 && beat < 20.7) p.emotion('joy', beat - 19);
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
        if (weapon == 'fist' || weapon == 'sword')
          px += math.max(0, ex - px - 185 * s) * smooth(age / .55);
        e.emotion('fear', age);
      }
      if (phase == 'impact') {
        if (weapon == 'fist' || weapon == 'sword')
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
        if (enemyWeapon == 'fist' || enemyWeapon == 'sword')
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
      if (phase == 'enemy-flight' && data['intent'] == 'windup') {
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
        if (enemyWeapon == 'fist' || enemyWeapon == 'sword')
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
    if (!reduced &&
        !{'impact', 'reply', 'counter-hit'}.contains(phase) &&
        age < .14) {
      final blend = smooth(age / .14);
      if (previousPlayer != null) p.blendFrom(previousPlayer!, blend);
      if (previousEnemy != null) e.blendFrom(previousEnemy!, blend);
    }
    if (!arena) {
      final gear = data['equipped'];
      if (gear is List && gear.isNotEmpty && p.weapon.isEmpty) {
        p.weapon = gear.first as String;
        p.deploy = .58;
        p.armR = -.85;
      }
    }
    player.travel(px + p.x * s * player.facing, s, dt);
    enemy.travel(ex - e.x * s, s, dt);
    void style(GameActor actor, String id) {
      final pose = actor.pose, f = pose.extra;
      final profile=robotProfiles[id] ?? robotProfiles['spark']!;
      final construction=profile['construction'] as String;
      pose.headY+=(profile['headY'] as num).toDouble()+117;
      for(var i=0;i<16;i++) {
        final stride=actor.motor.distance/22;
        f['joint$i']=math.sin(stride+(i%2)*math.pi)*.35;
        if(actor.mobility=='hexapod') f['joint$i']=math.sin(stride+i*math.pi)*.42;
        if(actor.mobility=='quadruped') f['joint$i']=math.sin(stride+[0,math.pi,math.pi,0][i%4])*.36;
        if(i>=8) f['joint$i']=math.max(0,math.sin(stride+(i%2)*math.pi))*.55;
        if(actor.mobility=='flight') f['joint$i']=math.sin(clock*6+i*math.pi)*.4;
        if({'gyro','reactor','sun','clock','storm','magnet','hologram'}.contains(construction))
          f['joint$i']=i*math.pi/6+clock*(construction=='clock' ? .14 : .32);
        if(construction=='octopus') f['joint$i']=math.sin(clock*2.5-i*.65)*.23;
        if(construction=='serpent') f['joint$i']=math.sin(clock*3.3-i*.7)*.28;
        if(construction=='medic' && i>=4 && i<8) f['joint$i']=clock*24;
        if(construction=='driller' && i==4) f['joint$i']=clock*(phase=='flight'?35:8);
        if(construction=='transformer' && i>=2 && i<=3) f['joint$i']=(i==2?-1:1)*(.16+pose.deploy*.8);
      }
      for(var i=0;i<8;i++) f['segmentY$i']=55+math.sin(clock*3.3-i*.7)*13;
      f['joint14']=actor.motor.distance/17+clock*.5;
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
    style(enemy, data['enemy'] as String? ?? 'flora');
    final modules=(data['modules'] as List? ?? const []).cast<String>();
    for(final entry in {
      'modArmor':const ['alloy','ceramic'],'modCore':const ['reactor','capacitor'],
      'modDrive':const ['servo','gyroscope'],'modDefense':const ['barrier','insulator'],
      'modGadget':const ['scope','overdrive'],
    }.entries) {
      player.pose.extra[entry.key]=modules.any(entry.value.contains)?1:0;
    }
    pendingBurst?.call(); pendingBurst=null;
    final autoZoom = reduced
        ? 1.0
        : arena && (phase == 'approach' || visibleShot)
        ? (activeWeapon == 'sniper' ? 1.09 : 1.035)
        : 1.0;
    final target = zoomTarget * autoZoom;
    zoom += (target - zoom) * (1 - math.exp(-10 * dt));
    notifyListeners();
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

  Offset target(GameActor a) => Offset(a.center, floor - 150 * scale);
  void camera(double value) {
    zoomTarget = value.clamp(1.0, 1.9);
    inspecting = zoomTarget > 1.05;
    if (!inspecting) pan = Offset.zero;
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
  final rive.File file;
  final scene = GameSceneClock();
  _GameRig? player, enemy;
  String enemyIdentity='';
  bool resetTime = true, disposed = false;
  @override
  void artboardChanged(rive.Artboard artboard) {
    player?.dispose(ownBoard: true);
    enemy?.dispose(ownBoard: true);
    player = _GameRig(file, artboard);
    enemyIdentity=scene.data['enemy'] as String? ?? 'flora';
    enemy = _GameRig(file, file.artboard(enemyIdentity=='spark'?'Spark':enemyIdentity) ?? file.artboard('Spark')!);
  }

  @override
  bool advance(double elapsedSeconds) {
    if (disposed || scene.suspended || scene.data['paused'] == true)
      return false;
    final dt = resetTime || !elapsedSeconds.isFinite
        ? 0.0
        : math.max(0.0, elapsedSeconds);
    resetTime = false;
    final desired=scene.data['enemy'] as String? ?? 'flora';
    if(scene.arena && desired!=enemyIdentity) {
      enemy?.dispose(ownBoard:true);
      enemyIdentity=desired;
      enemy=_GameRig(file,file.artboard(desired=='spark'?'Spark':desired) ?? file.artboard('Spark')!);
    }
    scene.advance(dt);
    player?.advance(
      scene.player,
      dt,
      scene.gaze,
      robotColor(scene.data['accent']),
    );
    if (scene.arena)
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
    if(disposed)return;
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
    void draw(_GameRig? rig, GameActor actor) {
      if (rig == null) return;
      final s = scene.scale, face = actor.facing;
      renderer.save();
      renderer.transform(
        rive.Mat2D.fromScaleAndTranslation(
          s * face,
          s,
          actor.center - (210 + actor.pose.x) * s * face,
          scene.floor - 402 * s,
        ),
      );
      rig.board.draw(renderer);
      renderer.restore();
    }

    draw(player, scene.player);
    if (scene.arena) draw(enemy, scene.enemy);
    renderer.restore();
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
  const GameSceneView({super.key, required this.file, required this.painter});
  final rive.File file;
  final GameScenePainter painter;
  @override
  State<GameSceneView> createState() => _GameSceneViewState();
}

class _GameSceneViewState extends State<GameSceneView> {
  double startZoom = 1;
  GameSceneClock get scene => widget.painter.scene;
  @override
  Widget build(BuildContext context) => RepaintBoundary(
    child: MouseRegion(
      onHover: (e) => scene.gaze = Offset(
        (e.localPosition.dx / scene.viewport.width - .5) * 12,
        (e.localPosition.dy / scene.viewport.height - .5) * 8,
      ),
      onExit: (_) => scene.gaze = Offset.zero,
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: (_) => scene.audio.unlock(),
        onPointerSignal: (e) {
          if (e is PointerScrollEvent && scene.expanded)
            scene.camera(scene.zoomTarget - e.scrollDelta.dy * .0015);
        },
        child: GestureDetector(
          // No tap recognizer: the workshop's existing Flet feed tap still wins.
          onScaleStart: scene.expanded
              ? (_) {
                  startZoom = scene.zoomTarget;
                }
              : null,
          onScaleUpdate: scene.expanded
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
              rive.RiveFileWidget(file: widget.file, painter: widget.painter,
                artboardName:scene.data['robot']=='spark'?'Spark':scene.data['robot'] as String?),
              IgnorePointer(
                child: CustomPaint(painter: GameEffectsPainter(scene)),
              ),
              if (scene.expanded && !scene.arena)
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
                  visualDensity: VisualDensity.compact,
                  onPressed: () => setState(() {
                    scene.audio.muted = !scene.audio.muted;
                    if (scene.audio.muted) scene.audio.pause();
                  }),
                  icon: Icon(
                    scene.audio.muted
                        ? Icons.volume_off_rounded
                        : Icons.volume_up_rounded,
                    size: 19,
                    color: const Color(0xFF63818F),
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
      for (var i = 0; i < 2; i++) {
        canvas.save();
        canvas.translate(size.width * (i == 0 ? .12 : .89), size.height * .74);
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
    }

    shield(scene.player);
    if (scene.arena) shield(scene.enemy);
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
    if (scene.visibleShot) {
      final actor = scene.enemyShot ? scene.enemy : scene.player;
      final defender = scene.enemyShot ? scene.player : scene.enemy;
      final type = scene.activeWeapon, t = scene.progress;
      final from = scene.muzzle(actor, type), to = scene.target(defender);
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
      } else if ({'laser','repair','ion'}.contains(type)) {
        final beam = Offset.lerp(from, to, math.min(1, t * 3))!;
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = (type=='repair'?const Color(0x447AFFBE):type=='ion'?const Color(0x448EA5FF):const Color(0x44FF6BAD))
            ..style = PaintingStyle.stroke
            ..strokeWidth = 22 * s,
        );
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = (type=='repair'?const Color(0xFF86FFD3):type=='ion'?const Color(0xFFBBA6FF):const Color(0xFFFF8DBE))
            ..strokeWidth = 6 * s,
        );
        canvas.drawLine(
          from,
          beam,
          paint
            ..color = Colors.white
            ..strokeWidth = 2 * s,
        );
      } else if ({'electric','magnetic','emp'}.contains(type)) {
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
        if(type!='electric') {
          canvas.drawCircle(end,(12+26*t)*s,paint..color=const Color(0xBBAE92FF)..style=PaintingStyle.stroke..strokeWidth=3*s);
          canvas.drawCircle(end,(5+13*t)*s,paint..color=const Color(0xDDDEBAFF)..strokeWidth=2*s);
        }
      } else if (type == 'flame' || type=='cryo') {
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
                type=='cryo'?const Color(0xDDE8FFFF):const Color(0xDDFFF7BD),
                type=='cryo'?const Color(0x7785CEFF):const Color(0x77F46B48),
                along,
              )!
              ..style = PaintingStyle.fill,
          );
        }
      } else if (type == 'machinegun' || type=='blaster') {
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
      } else if (type=='disc' || type=='grenade') {
        final position=Offset.lerp(from,to,t)!+Offset(0,type=='grenade'?-math.sin(t*math.pi)*60*s:0);
        canvas.save();canvas.translate(position.dx,position.dy);canvas.rotate(scene.clock*30);
        canvas.drawOval(Rect.fromCenter(center:Offset.zero,width:34*s,height:(type=='disc'?9:28)*s),paint..style=PaintingStyle.fill..color=const Color(0xFFBBD9EC));
        canvas.drawCircle(Offset.zero,5*s,paint..color=color);canvas.restore();
        glow(position,7*s,color);
      } else if (type == 'fist' || type=='drill') {
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
