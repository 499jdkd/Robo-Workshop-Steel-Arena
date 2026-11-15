import 'dart:convert';

import 'package:flet/flet.dart';
import 'package:flet_rive/flet_rive.dart' as robot;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rive/rive.dart' as rive;

/// A comparable, repeatable CPU/layout benchmark in the Windows test engine.
/// It is NOT a physical screen FPS or mobile GPU measurement.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final results = <String, dynamic>{
    'measurement':
        'Flutter Windows test engine, debug; pump CPU/layout cost, not device FPS',
    'rive_renderer':
        'Factory.flutter (real Rive native import and state machine)',
    'frames_per_case': 600,
  };
  setUpAll(() async {
    await rive.RiveNative.init();
  });
  for (final mode in ['legacy', 'rive']) {
    testWidgets('$mode: 600 comparable frames', (tester) async {
      tester.view.physicalSize = const Size(600, 440);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final backend = FletBackend(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [robot.Extension()],
      );
      backend.pageSize = const Size(600, 440);
      backend.isLoading = false;
      final frames =
          jsonDecode(File('../assets/legacy_frames.json').readAsStringSync())
              as List;
      final initial = mode == 'legacy'
          ? Map<String, dynamic>.from(frames.first)
          : <String, dynamic>{
              '_c': 'RobotRive',
              '_i': 9901,
              'src': File('../assets/spark.riv').absolute.path,
              'width': 600,
              'height': 440,
              'renderer': 'flutter',
              'action': 'move',
              'command_id': 1,
            };
      final control = Control.fromMap(initial, backend);
      Widget scene(int frame) {
        return SizedBox(
          width: 600,
          height: 440,
          child: ControlWidget(control: control),
        );
      }

      Widget app(int frame) => ChangeNotifierProvider<FletBackend>.value(
        value: backend,
        child: MaterialApp(
          home: Scaffold(body: Center(child: scene(frame))),
        ),
      );
      await tester.pumpWidget(app(0));
      for (
        var wait = 0;
        wait < 150 &&
            mode == 'rive' &&
            find.byType(robot.RobotSceneView).evaluate().isEmpty;
        wait++
      ) {
        await tester.runAsync(() async {
          await Future<void>.delayed(const Duration(milliseconds: 20));
        });
        await tester.pump();
      }
      for (var i = 0; i < 90; i++) {
        await tester.pump(const Duration(microseconds: 16667));
      }
      final micros = <int>[];
      for (var frame = 0; frame < 600; frame++) {
        final watch = Stopwatch()..start();
        if (mode == 'legacy' && frame % 60 == 0) {
          final update =
              Map<String, dynamic>.from(frames[(frame ~/ 60) % frames.length])
                ..remove('_c')
                ..remove('_i');
          control.update(update, shouldNotify: true);
        }
        await tester.pump(const Duration(microseconds: 16667));
        watch.stop();
        micros.add(watch.elapsedMicroseconds);
      }
      expect(find.byType(ErrorControl), findsNothing);
      if (mode == 'rive') {
        expect(find.byType(robot.RobotSceneView), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
      micros.sort();
      results[mode] = {
        'median_pump_ms': micros[micros.length ~/ 2] / 1000,
        'p95_pump_ms': micros[(micros.length * .95).floor()] / 1000,
        'max_pump_ms': micros.last / 1000,
        'pumps_over_16_67ms': micros.where((n) => n > 16667).length,
      };
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    }, timeout: const Timeout(Duration(minutes: 3)));
  }
  tearDownAll(() {
    final target = File(
      '../../../.cache/rive-research/flutter-cpu-benchmark.json',
    );
    target.parent.createSync(recursive: true);
    target.writeAsStringSync(
      const JsonEncoder.withIndent('  ').convert(results),
    );
    debugPrint(jsonEncode(results));
  });
}
