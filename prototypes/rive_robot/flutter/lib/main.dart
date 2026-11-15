import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flet_rive/flet_rive.dart';
import 'package:rive/rive.dart' as rive;

import 'frame_budget.dart';
import 'profile_report.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (const bool.fromEnvironment('RIVE_LOG_FPS')) {
    FlutterError.onError = (details) {
      FlutterError.presentError(details);
      unawaited(
        reportProfile({
          'kind': 'error',
          'message': details.exceptionAsString(),
        }),
      );
    };
  }
  await rive.RiveNative.init();
  runApp(const RobotLab());
}

class RobotLab extends StatefulWidget {
  const RobotLab({super.key});
  @override
  State<RobotLab> createState() => _RobotLabState();
}

class _RobotLabState extends State<RobotLab> {
  rive.File? _file;
  RobotScenePainter? _painter;
  String? _error;
  int _command = 0;
  bool _arena = const bool.fromEnvironment('RIVE_START_ARENA');
  bool _auto = true;
  bool _reduced = false;
  bool _metrics = const bool.fromEnvironment('RIVE_START_FPS');
  Timer? _profileCycle;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final bytes = await rootBundle.load('assets/spark.riv');
      final file = await rive.File.decode(
        bytes.buffer.asUint8List(),
        riveFactory: rive.Factory.rive,
      );
      if (!mounted) {
        file?.dispose();
        return;
      }
      if (file == null) throw StateError('Rive runtime could not import Spark');
      setState(() {
        _file = file;
        _painter = RobotScenePainter(file);
        _painter!.scene.arena = _arena;
      });
      if (const bool.fromEnvironment('RIVE_LOG_FPS')) {
        debugPrint('RIVE_LAB_READY renderer=rive arena=$_arena');
      }
      if (const bool.fromEnvironment('RIVE_PROFILE_COMBAT')) {
        const actions = [
          'attack',
          'charge',
          'defend',
          'hit',
          'victory',
          'idle',
        ];
        _profileCycle = Timer.periodic(const Duration(seconds: 2), (timer) {
          if (!mounted) return;
          final action = actions[(timer.tick - 1) % actions.length];
          _painter!.command(action, ++_command);
          if (action == 'hit') {
            final scene = _painter!.scene;
            scene.effects.burst(
              scene.playerX,
              scene.floor - 135 * scene.scale,
              count: 40,
            );
          }
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = '$error';
        });
      }
    }
  }

  @override
  void dispose() {
    _profileCycle?.cancel();
    _painter?.dispose();
    _file?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: ThemeData.dark(
      useMaterial3: true,
    ).copyWith(scaffoldBackgroundColor: const Color(0xFF0A1525)),
    home: Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxHeight < 460;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (!compact) ...[
                    const Text(
                      'Искра / Motion Lab',
                      style: TextStyle(
                        fontSize: 25,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 5),
                    const Text(
                      'Один прототип · сохранение игры не используется',
                      style: TextStyle(color: Color(0xFFAAC4D8), fontSize: 12),
                    ),
                    const SizedBox(height: 14),
                  ],
                  Expanded(
                    child: _painter != null
                        ? Stack(
                            fit: StackFit.expand,
                            children: [
                              RobotSceneView(file: _file!, painter: _painter!),
                              if (_metrics)
                                const Positioned(
                                  top: 38,
                                  left: 12,
                                  child: IgnorePointer(child: FrameBudgetHud()),
                                ),
                            ],
                          )
                        : Center(
                            child: _error != null
                                ? const Text(
                                    'Нужен экспорт Spark из Rive.\nЗапусти tools/prepare_rive_prototype.py после rive login.',
                                    textAlign: TextAlign.center,
                                  )
                                : const CircularProgressIndicator(),
                          ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: compact ? 90 : 170,
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          Wrap(
                            spacing: 7,
                            runSpacing: 5,
                            children: [
                              for (final state in [
                                'idle',
                                'move',
                                'attack',
                                'defend',
                                'charge',
                                'hit',
                                'victory',
                                'defeat',
                              ])
                                FilledButton.tonal(
                                  onPressed: _painter == null
                                      ? null
                                      : () {
                                          _painter!.command(state, ++_command);
                                        },
                                  child: Text(state),
                                ),
                            ],
                          ),
                          Wrap(
                            spacing: 16,
                            children: [
                              _toggle('Арена', _arena, (v) {
                                setState(() {
                                  _arena = v;
                                });
                                _painter?.scene.arena = v;
                                _painter?.scheduleRepaint();
                              }),
                              _toggle('Патруль', _auto, (v) {
                                setState(() {
                                  _auto = v;
                                });
                                _painter?.scene.player.autonomous = v;
                              }),
                              _toggle('Меньше движения', _reduced, (v) {
                                setState(() {
                                  _reduced = v;
                                });
                                _painter?.scene.player.reducedMotion = v;
                              }),
                              _toggle('FPS', _metrics, (v) {
                                setState(() {
                                  _metrics = v;
                                });
                              }),
                            ],
                          ),
                          const Text(
                            'Осмотр: двойное нажатие, щипок, перетаскивание или колесо мыши.',
                            style: TextStyle(
                              fontSize: 11,
                              color: Color(0xFFAAC4D8),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    ),
  );

  Widget _toggle(String text, bool value, ValueChanged<bool> onChanged) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(text, style: const TextStyle(fontSize: 12)),
      Switch(value: value, onChanged: _painter == null ? null : onChanged),
    ],
  );
}
