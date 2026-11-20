import 'dart:math' as math;

import 'package:flet/flet.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:rive/rive.dart' as rive;

import 'robot/motion_model.dart';

/// One opt-in presentation control. Commands never award damage or game rewards.
class RobotRiveControl extends StatefulWidget {
  const RobotRiveControl({super.key, required this.control});
  final Control control;
  @override
  State<RobotRiveControl> createState() => _RobotRiveControlState();
}

class _RobotRiveControlState extends State<RobotRiveControl> {
  Future<rive.File?>? _loading;
  rive.File? _file;
  String? _source;
  String? _renderer;
  int _generation = 0;
  RobotScenePainter? _painter;

  void _load(String source, String renderer) {
    if (source == _source && renderer == _renderer) return;
    _source = source;
    _renderer = renderer;
    final generation = ++_generation;
    _painter?.dispose();
    _painter = null;
    // Old widgets are unmounted at the end of this build before file disposal.
    final previous = _file;
    _file = null;
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.dispose());
    final asset = widget.control.backend.getAssetSource(source);
    final factory = renderer == 'flutter'
        ? rive.Factory.flutter
        : rive.Factory.rive;
    _loading = rive.RiveNative.init()
        .then(
          (_) => (asset.isFile
              ? rive.File.path(asset.path, riveFactory: factory)
              : rive.File.url(asset.path, riveFactory: factory)),
        )
        .then((file) {
          if (!mounted || generation != _generation) {
            file?.dispose();
            return null;
          }
          _file = file;
          return file;
        });
  }

  @override
  Widget build(BuildContext context) {
    _load(
      widget.control.getString('src', 'spark.riv')!,
      widget.control.getString('renderer', 'rive')!,
    );
    return LayoutControl(
      control: widget.control,
      child: FutureBuilder<rive.File?>(
        key: ValueKey('$_source|$_renderer'),
        future: _loading,
        builder: (context, snapshot) {
          if (snapshot.hasError ||
              (snapshot.connectionState == ConnectionState.done &&
                  snapshot.data == null)) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Rive prototype file is not available.\nRun rive animation/rive/spark --publish, then the prototype setup script.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          final file = snapshot.data;
          if (file == null)
            return const Center(child: CircularProgressIndicator());
          final painter = _painter ??= RobotScenePainter(file);
          painter.scene.player.autonomous = widget.control.getBool(
            'autonomous',
            true,
          )!;
          painter.scene.player.reducedMotion =
              MediaQuery.disableAnimationsOf(context) ||
              widget.control.getBool('reduced_motion', false)!;
          painter.scene.arena = widget.control.getBool('arena', false)!;
          painter.scene.paused = widget.control.getBool('paused', false)!;
          painter.command(
            widget.control.getString('action', 'idle')!,
            widget.control.getInt('command_id', 0)!,
          );
          return RobotSceneView(file: file, painter: painter);
        },
      ),
    );
  }

  @override
  void dispose() {
    _generation++;
    _painter?.dispose();
    _file?.dispose();
    super.dispose();
  }
}

class SceneClock extends ChangeNotifier {
  final player = RobotPresentation();
  final enemy = RobotPresentation()
    ..autonomous = false
    ..arena = true;
  final effects = SparkEffects();
  bool arena = false;
  bool paused = false;
  bool suspended = false;
  bool resetClock = true;
  bool inspected = false;
  double zoom = 1;
  double zoomTarget = 1;
  Offset pan = Offset.zero;
  Offset gaze = Offset.zero;
  double shotAge = 99;
  bool shotHit = true;
  Size viewport = const Size(720, 420);

  bool get reducedMotion => player.reducedMotion;
  double get floor => viewport.height * .84;
  double get scale => math.min(
    viewport.height * .76 / 340,
    viewport.width * (arena ? .37 : .56) / 240,
  );
  double get playerX => arena
      ? viewport.width * .23
      : viewport.width * .5 + player.motor.x * scale;
  double get enemyX => viewport.width * .77;
  double get shotProgress => ((shotAge - .333) / 1).clamp(0, 1);
  bool get shotVisible => arena && shotAge >= .333 && shotAge < 1.333;

  void tick(double seconds) {
    if (paused || suspended || !seconds.isFinite || seconds <= 0) return;
    // Lifecycle/TickerMode pauses the clock; ordinary slow frames retain their
    // elapsed time so movement speed stays independent of refresh rate.
    final dt = seconds;
    player.arena = arena;
    player.inspecting = inspected;
    player.advance(
      dt,
      span: math.min(130, math.max(0, (viewport.width / scale - 250) / 2 - 24)),
    );
    enemy.reducedMotion = reducedMotion;
    enemy.advance(dt);
    effects.advance(dt);
    zoom = reducedMotion
        ? zoomTarget
        : zoomTarget + (zoom - zoomTarget) * math.exp(-10 * dt);
    final previousAge = shotAge;
    shotAge += dt;
    if (arena && !shotHit && previousAge < 1.333 && shotAge >= 1.333) {
      shotHit = true;
      enemy.request(RobotAction.hit, enemy.lastCommand + 1);
      effects.burst(enemyX, floor - 135 * scale, reducedMotion: reducedMotion);
    }
    notifyListeners();
  }

  void inspect(Offset point) {
    inspected = !inspected;
    player.inspecting = inspected;
    zoomTarget = inspected ? 1.55 : 1;
    if (reducedMotion) zoom = zoomTarget;
    pan = inspected
        ? Offset((viewport.width / 2 - point.dx) * .25, 10)
        : Offset.zero;
    notifyListeners();
  }

  void setZoom(double value) {
    zoomTarget = value.clamp(1, 2.2);
    inspected = zoomTarget > 1.01;
    player.inspecting = inspected;
    if (reducedMotion) zoom = zoomTarget;
    if (zoomTarget == 1) {
      pan = Offset.zero;
      inspected = false;
    }
    notifyListeners();
  }
}

class _RiveRobot {
  _RiveRobot(rive.File file, this.board, this.presentation) {
    machine = board.stateMachine('RobotMotion')!;
    vm = file.createDefaultViewModelInstance(board)!;
    machine.bindViewModelInstance(vm);
    for (final name in [
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
      fields[name] = vm.number(name)!;
    }
    machine.advanceAndApply(0);
  }
  final rive.Artboard board;
  final RobotPresentation presentation;
  late final rive.StateMachine machine;
  late final rive.ViewModelInstance vm;
  final fields = <String, rive.ViewModelInstanceNumber>{};
  void advance(double dt, Offset gaze) {
    fields['mode']!.value = presentation.visualAction.index.toDouble();
    fields['wheelAngle']!.value = presentation.motor.wheelAngle;
    fields['lookX']!.value = gaze.dx;
    fields['lookY']!.value = gaze.dy;
    for (var i = 0; i < 16; i++) {
      final p = treadAt(
        i * trackLength / 16 + presentation.motor.trackDistance,
      );
      fields['tread${i}X']!.value = p.x;
      fields['tread${i}Y']!.value = p.y;
      fields['tread${i}R']!.value = p.rotation;
    }
    machine.advanceAndApply(dt);
  }

  void dispose({bool ownBoard = false}) {
    machine.dispose();
    for (final field in fields.values) {
      field.dispose();
    }
    vm.dispose();
    if (ownBoard) board.dispose();
  }
}

base class RobotScenePainter extends rive.ArtboardPainter
    with rive.RiveTickerAwarePainterMixin {
  RobotScenePainter(this.file);
  final rive.File file;
  final scene = SceneClock();
  _RiveRobot? _player, _enemy;
  bool _disposed = false;

  @override
  void artboardChanged(rive.Artboard artboard) {
    _player?.dispose();
    _enemy?.dispose(ownBoard: true);
    _player = _RiveRobot(file, artboard, scene.player);
    _enemy = _RiveRobot(file, file.artboard('Spark')!, scene.enemy);
  }

  void command(String name, int command) {
    final action =
        RobotAction.values.where((a) => a.name == name).firstOrNull ??
        RobotAction.idle;
    if (!scene.player.request(action, command)) return;
    if (action == RobotAction.attack) {
      scene.shotAge = 0;
      scene.shotHit = false;
    } else if (action == RobotAction.hit) {
      scene.effects.burst(
        scene.playerX,
        scene.floor - 135 * scene.scale,
        reducedMotion: scene.reducedMotion,
      );
    } else if (action == RobotAction.victory) {
      scene.effects.burst(
        scene.playerX,
        scene.floor - 250 * scene.scale,
        count: 24,
        reducedMotion: scene.reducedMotion,
      );
    }
    scheduleRepaint();
  }

  @override
  bool advance(double elapsedSeconds) {
    if (_disposed || scene.paused || scene.suspended) return false;
    final dt =
        !scene.resetClock && elapsedSeconds.isFinite && elapsedSeconds > 0
        ? elapsedSeconds
        : 0.0;
    scene.resetClock = false;
    scene.tick(dt);
    _player?.advance(scene.reducedMotion ? .1 : dt, scene.gaze);
    if (scene.arena)
      _enemy?.advance(scene.reducedMotion ? .1 : dt, Offset.zero);
    return !scene.reducedMotion;
  }

  @override
  void paint(rive.Renderer renderer, Size size, double paintPixelRatio) {
    scene.viewport = size;
    final camera = scene.reducedMotion ? 0.0 : scene.effects.shake;
    renderer.save();
    renderer.transform(
      rive.Mat2D.fromScaleAndTranslation(
        scene.zoom,
        scene.zoom,
        size.width * (1 - scene.zoom) / 2 + scene.pan.dx + camera,
        size.height * (1 - scene.zoom) / 2 + scene.pan.dy,
      ),
    );
    void draw(_RiveRobot? robot, double x, double facing) {
      if (robot == null) return;
      final s = scene.scale;
      renderer.save();
      renderer.transform(
        rive.Mat2D.fromScaleAndTranslation(
          s * facing,
          s,
          x - 210 * s * facing,
          scene.floor - 402 * s,
        ),
      );
      robot.board.draw(renderer);
      renderer.restore();
    }

    draw(_player, scene.playerX, scene.arena ? 1 : scene.player.motor.facing);
    if (scene.arena) draw(_enemy, scene.enemyX, -1);
    renderer.restore();
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _player?.dispose();
    _enemy?.dispose(ownBoard: true);
    scene.dispose();
    super.dispose();
  }
}

/// Repaints the Rive scene and effect canvas; never rebuilds Flet per frame.
class RobotSceneView extends StatefulWidget {
  const RobotSceneView({super.key, required this.file, required this.painter});
  final rive.File file;
  final RobotScenePainter painter;
  @override
  State<RobotSceneView> createState() => _RobotSceneViewState();
}

class _RobotSceneViewState extends State<RobotSceneView>
    with WidgetsBindingObserver {
  double _zoomAtStart = 1;
  SceneClock get scene => widget.painter.scene;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    scene.suspended = state != AppLifecycleState.resumed;
    if (!scene.suspended) {
      scene.resetClock = true;
      widget.painter.scheduleRepaint();
    }
  }

  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(22),
    child: MouseRegion(
      cursor: SystemMouseCursors.grab,
      onHover: (e) {
        scene.gaze = Offset(
          ((e.localPosition.dx / scene.viewport.width) - .5) * 8,
          ((e.localPosition.dy / scene.viewport.height) - .5) * 6,
        );
      },
      onExit: (_) {
        scene.gaze = Offset.zero;
      },
      child: Listener(
        onPointerSignal: (event) {
          if (event is PointerScrollEvent) {
            scene.setZoom(scene.zoomTarget - event.scrollDelta.dy * .0015);
            widget.painter.scheduleRepaint();
          }
        },
        child: GestureDetector(
          onDoubleTapDown: (e) {
            scene.inspect(e.localPosition);
            widget.painter.scheduleRepaint();
          },
          onScaleStart: (_) {
            _zoomAtStart = scene.zoomTarget;
          },
          onScaleUpdate: (e) {
            scene.setZoom(_zoomAtStart * e.scale);
            if (scene.zoomTarget > 1.01) {
              scene.pan = Offset(
                (scene.pan.dx + e.focalPointDelta.dx).clamp(-100, 100),
                (scene.pan.dy + e.focalPointDelta.dy).clamp(-80, 80),
              );
            }
            widget.painter.scheduleRepaint();
          },
          child: Stack(
            fit: StackFit.expand,
            children: [
              CustomPaint(painter: _SceneBackdrop(scene)),
              rive.RiveFileWidget(
                file: widget.file,
                painter: widget.painter,
                artboardName: 'Spark',
              ),
              IgnorePointer(child: CustomPaint(painter: _SceneEffects(scene))),
              Positioned(
                top: 14,
                left: 16,
                child: Text(
                  scene.arena ? 'ИСКРА / СПАРРИНГ' : 'ИСКРА / RIVE LAB',
                  style: const TextStyle(
                    color: Color(0xFFABCBDF),
                    fontSize: 11,
                    letterSpacing: 1.8,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Positioned(
                right: 10,
                bottom: 8,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      onPressed: () {
                        scene.setZoom(1);
                        widget.painter.scheduleRepaint();
                      },
                      tooltip: 'Сбросить камеру',
                      icon: const Icon(
                        Icons.center_focus_strong_rounded,
                        color: Colors.white70,
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        scene.inspect(
                          Offset(
                            scene.playerX,
                            scene.floor - 150 * scene.scale,
                          ),
                        );
                        widget.painter.scheduleRepaint();
                      },
                      tooltip: 'Осмотреть робота',
                      icon: const Icon(
                        Icons.zoom_in_rounded,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _SceneBackdrop extends CustomPainter {
  _SceneBackdrop(this.scene);
  final SceneClock scene;
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF233C51), Color(0xFF0A1525)],
        ).createShader(rect),
    );
    final grid = Paint()
      ..color = const Color(0x1227D9E6)
      ..strokeWidth = 1;
    final floor = size.height * .84;
    for (var x = -size.width; x < size.width * 2; x += 54) {
      canvas.drawLine(
        Offset(size.width / 2, floor - 36),
        Offset(x, size.height),
        grid,
      );
    }
    for (final f in [.0, .15, .38, .7, 1.0]) {
      final y = floor - 36 + (size.height - floor + 36) * f;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    for (var i = 0; i < 4; i++) {
      final x = size.width * (i + .5) / 4;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(
            center: Offset(x, size.height * .24),
            width: size.width * .12,
            height: 3,
          ),
          const Radius.circular(2),
        ),
        Paint()..color = const Color(0x5072D7EE),
      );
    }
    final glow = Paint()
      ..shader =
          const RadialGradient(
            colors: [Color(0x2534DFFF), Color(0x0034DFFF)],
          ).createShader(
            Rect.fromCircle(
              center: Offset(size.width * .5, size.height * .5),
              radius: size.height * .65,
            ),
          );
    canvas.drawRect(rect, glow);
  }

  @override
  bool shouldRepaint(covariant _SceneBackdrop oldDelegate) =>
      oldDelegate.scene != scene;
}

class _SceneEffects extends CustomPainter {
  _SceneEffects(this.scene) : super(repaint: scene);
  final SceneClock scene;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.translate(
      size.width / 2 * (1 - scene.zoom) +
          scene.pan.dx +
          (scene.reducedMotion ? 0 : scene.effects.shake),
      size.height / 2 * (1 - scene.zoom) + scene.pan.dy,
    );
    canvas.scale(scene.zoom);
    if (scene.shotVisible) {
      final progress = scene.shotProgress;
      final start = scene.playerX + 105 * scene.scale;
      final end = scene.enemyX - 65 * scene.scale;
      final x = start + (end - start) * progress;
      final y =
          scene.floor - 138 * scene.scale - math.sin(progress * math.pi) * 18;
      canvas.drawLine(
        Offset(x - 28, y + 2),
        Offset(x, y),
        Paint()
          ..color = const Color(0xBBFFCB65)
          ..strokeWidth = 5
          ..strokeCap = StrokeCap.round,
      );
      canvas.drawCircle(
        Offset(x, y),
        12,
        Paint()
          ..shader = const RadialGradient(
            colors: [Color(0xFFFFFBDB), Color(0xFFFFC65F), Color(0x00FFC65F)],
          ).createShader(Rect.fromCircle(center: Offset(x, y), radius: 12)),
      );
    }
    final paint = Paint()..strokeCap = StrokeCap.round;
    for (final p in scene.effects.particles) {
      paint
        ..color = Color.lerp(
          const Color(0xFFFFD270),
          const Color(0xFF85F8FF),
          p.hue,
        )!.withValues(alpha: p.opacity)
        ..strokeWidth = 2.4;
      canvas.drawLine(
        Offset(p.x, p.y),
        Offset(p.x - p.vx * .025, p.y - p.vy * .025),
        paint,
      );
    }
    if (scene.effects.flash > 0 && !scene.reducedMotion) {
      canvas.drawCircle(
        Offset(
          scene.arena ? scene.enemyX : scene.playerX,
          scene.floor - 135 * scene.scale,
        ),
        50 * (1 - scene.effects.flash) + 10,
        Paint()
          ..color = Color(
            0xFFFFEDAF,
          ).withValues(alpha: scene.effects.flash * .5)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3,
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _SceneEffects oldDelegate) =>
      oldDelegate.scene != scene;
}
