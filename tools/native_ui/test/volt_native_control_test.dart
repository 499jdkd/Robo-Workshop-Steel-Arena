import 'dart:convert';
import 'dart:async';
import 'dart:ui' as ui;
import 'package:flet/flet.dart';
import 'package:flet_rive/src/game_scene.dart';
import 'package:flet_rive/src/robot/rig_cache.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rive/rive.dart' as rive;

const invalidRivePath =
    'C:/Clicker/.cache/volt-refinement/this-rive-file-does-not-exist.riv';

class RecordingBackend extends FletBackend {
  RecordingBackend()
    : super(
        pageUri: Uri.parse('http://localhost'),
        assetsDir: '',
        multiView: false,
        extensions: [],
      ) {
    pageSize = const Size(390, 294);
    isLoading = false;
  }
  final assetRequests = <String>[];
  final events = <({String name, dynamic data})>[];
  @override
  AssetSource getAssetSource(String src) {
    assetRequests.add(src);
    return const AssetSource(path: invalidRivePath, isFile: true);
  }

  @override
  void triggerControlEvent(
    Control control,
    String eventName, [
    dynamic eventData,
  ]) {
    events.add((name: eventName, data: eventData));
  }
}

const basePayload = <String, dynamic>{
  'robot': 'volt',
  'arena': false,
  'mobility': 'hover',
  'action': 'idle',
  'phase': 'workshop',
  'event': '0',
  'sound': false,
  'accent': '#36DFFF',
};

Control control(
  RecordingBackend backend, {
  Map<String, dynamic> payload = basePayload,
}) => Control.fromMap({
  '_c': 'GameRive',
  '_i': 8723,
  'src': 'intentionally-invalid.riv',
  'payload': jsonEncode(payload),
  'renderer': 'flutter',
  'report_ready': true,
  'on_ready': true,
  'on_robot_tap': true,
  'width': 390,
  'height': 294,
}, backend);

Widget host(
  RecordingBackend backend,
  Control control, {
  bool visible = true,
  Key? boundary,
}) => ChangeNotifierProvider<FletBackend>.value(
  value: backend,
  child: MaterialApp(
    home: Scaffold(
      backgroundColor: const Color(0xFF10233F),
      body: Center(
        child: TickerMode(
          enabled: visible,
          child: RepaintBoundary(
            key: boundary,
            child: SizedBox(
              width: 390,
              height: 294,
              child: GameRiveControl(
                key: const ValueKey('native-volt-control'),
                control: control,
              ),
            ),
          ),
        ),
      ),
    ),
  ),
);

GameSceneClock scene(WidgetTester tester) =>
    tester.widget<GameSceneView>(find.byType(GameSceneView)).nativeScene!;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  tearDown(() async => clearIdleRigCache());

  testWidgets(
    'Volt paints immediately with invalid Rive source and reports real Canvas paint',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      final boundary = GlobalKey();
      await tester.pumpWidget(host(backend, ctrl, boundary: boundary));
      expect(find.byType(GameSceneView), findsOneWidget);
      expect(find.byType(rive.RiveFileWidget), findsNothing);
      final view = tester.widget<GameSceneView>(find.byType(GameSceneView));
      expect(view.file, isNull);
      expect(view.painter, isNull);
      expect(scene(tester).playerVoltFrame, isNotNull);
      expect(
        backend.assetRequests,
        isEmpty,
        reason:
            'No Rive file, VM or source resolution is needed for Volt workshop',
      );
      expect(backend.events.where((e) => e.name == 'ready').length, 1);
      final data = backend.events.first.data['data'] as Map;
      expect(data['renderer'], 'flutter');
      expect(data['model_renderer'], 'flutter-canvas-articulated');
      expect(data['rig_load_ms'], 0);
      expect(data['model_warm_ms'], greaterThanOrEqualTo(0));
      final render =
          boundary.currentContext!.findRenderObject() as RenderRepaintBoundary;
      await tester.runAsync(() async {
        final image = await render.toImage(pixelRatio: 2);
        final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
        final out = Directory('../../.cache/volt-refinement/fast-path')
          ..createSync(recursive: true);
        File(
          '${out.path}/first-paint.png',
        ).writeAsBytesSync(png.buffer.asUint8List());
        image.dispose();
      });
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    },
  );

  testWidgets(
    'native frames repaint without recreating widgets or emitting Flet events',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      await tester.pumpWidget(host(backend, ctrl));
      final before = tester.widget<GameSceneView>(find.byType(GameSceneView));
      final clock = scene(tester);
      final age = clock.clock;
      for (var i = 0; i < 120; i++)
        await tester.pump(const Duration(milliseconds: 16));
      expect(clock.clock, greaterThan(age + 1.8));
      expect(
        identical(
          before,
          tester.widget<GameSceneView>(find.byType(GameSceneView)),
        ),
        isTrue,
        reason: 'The ticker must notify only the local CustomPainter',
      );
      expect(backend.events.length, 1);
      expect(backend.assetRequests, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
      expect(tester.binding.transientCallbackCount, 0);
    },
  );

  testWidgets(
    'paused payload and hidden tabs stop the ticker and resume without catch-up',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      await tester.pumpWidget(host(backend, ctrl));
      await tester.pump(const Duration(milliseconds: 16));
      final clock = scene(tester);
      ctrl.properties['payload'] = jsonEncode({...basePayload, 'paused': true});
      await tester.pumpWidget(host(backend, ctrl));
      final pausedAt = clock.clock;
      await tester.pump(const Duration(seconds: 5));
      expect(clock.clock, pausedAt);
      expect(tester.binding.transientCallbackCount, 0);
      ctrl.properties['payload'] = jsonEncode(basePayload);
      await tester.pumpWidget(host(backend, ctrl, visible: false));
      expect(clock.hidden, isTrue);
      await tester.pump(const Duration(seconds: 5));
      expect(clock.clock, pausedAt);
      await tester.pumpWidget(host(backend, ctrl));
      await tester.pump(const Duration(seconds: 2));
      expect(clock.clock - pausedAt, lessThanOrEqualTo(.041));
      await tester.pump(const Duration(milliseconds: 16));
      expect(clock.clock, greaterThan(pausedAt));
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    },
  );

  testWidgets(
    'Android lifecycle suspends the local loop and resets elapsed time on resume',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      await tester.pumpWidget(host(backend, ctrl));
      await tester.pump(const Duration(milliseconds: 16));
      final clock = scene(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      final pausedAt = clock.clock;
      await tester.pump(const Duration(seconds: 3));
      expect(clock.clock, pausedAt);
      expect(clock.suspended, isTrue);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump(const Duration(seconds: 3));
      expect(clock.clock, pausedAt);
      await tester.pump(const Duration(milliseconds: 16));
      expect(clock.clock, greaterThan(pausedAt));
      expect(clock.clock - pausedAt, lessThanOrEqualTo(.041));
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    },
  );

  testWidgets(
    'workshop and inspection share pointer reactions without demo rewards',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      await tester.pumpWidget(host(backend, ctrl));
      final clock = scene(tester);
      final top = tester.getTopLeft(find.byType(GameSceneView));
      await tester.tapAt(top + clock.target(clock.player));
      expect(backend.events.where((e) => e.name == 'robot_tap').length, 1);
      expect(clock.localAction, isNotEmpty);
      await tester.tapAt(top + const Offset(375, 280));
      expect(clock.manualPosition, isTrue);
      expect(backend.events.where((e) => e.name == 'robot_tap').length, 1);
      ctrl.properties['payload'] = jsonEncode({
        ...basePayload,
        'demonstration': true,
      });
      await tester.pumpWidget(host(backend, ctrl));
      await tester.tapAt(top + clock.target(clock.player));
      expect(backend.events.where((e) => e.name == 'robot_tap').length, 1);
      expect(backend.assetRequests, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    },
  );

  testWidgets(
    'a paused or hidden first mount still samples a detailed static model',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend, payload: {...basePayload, 'paused': true});
      await tester.pumpWidget(host(backend, ctrl, visible: false));
      expect(scene(tester).playerVoltFrame, isNotNull);
      expect(scene(tester).clock, 0);
      expect(backend.assetRequests, isEmpty);
      expect(backend.events, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
    },
  );

  testWidgets(
    'other characters and arena Volt keep the existing Rive loading path',
    (tester) async {
      for (final payload in [
        {...basePayload, 'robot': 'spark'},
        {...basePayload, 'arena': true, 'enemy': 'spark'},
      ]) {
        final backend = RecordingBackend();
        final ctrl = control(backend, payload: payload);
        // A pending cache lease proves the actual Rive loader path without
        // initializing a platform DLL in this Canvas-only control test.
        final pending = Completer<rive.File?>();
        final cacheLease = acquireRig(
          '$invalidRivePath|flutter',
          () => pending.future,
        );
        await tester.pumpWidget(host(backend, ctrl));
        expect(backend.assetRequests, ['intentionally-invalid.riv']);
        expect(find.byType(GameSceneView), findsNothing);
        await tester.pumpWidget(const SizedBox.shrink());
        pending.complete(null);
        cacheLease.release();
        backend.dispose();
        await tester.runAsync(clearIdleRigCache);
      }
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'rapid mount/unmount and stale Rive futures cannot replace native Volt',
    (tester) async {
      final backend = RecordingBackend();
      final ctrl = control(backend);
      for (var i = 0; i < 12; i++) {
        await tester.pumpWidget(host(backend, ctrl));
        await tester.pump(const Duration(milliseconds: 16));
        await tester.pumpWidget(const SizedBox.shrink());
        expect(tester.binding.transientCallbackCount, 0);
      }
      await tester.pumpWidget(host(backend, ctrl));
      final pending = Completer<rive.File?>();
      final cacheLease = acquireRig(
        '$invalidRivePath|flutter',
        () => pending.future,
      );
      ctrl.properties['payload'] = jsonEncode({
        ...basePayload,
        'robot': 'spark',
      });
      await tester.pumpWidget(host(backend, ctrl));
      ctrl.properties['payload'] = jsonEncode(basePayload);
      await tester.pumpWidget(host(backend, ctrl));
      pending.complete(null);
      cacheLease.release();
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 80)),
      );
      await tester.pump();
      expect(find.byType(GameSceneView), findsOneWidget);
      expect(scene(tester).data['robot'], 'volt');
      expect(find.byType(rive.RiveFileWidget), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      backend.dispose();
      await tester.runAsync(clearIdleRigCache);
      expect(tester.binding.transientCallbackCount, 0);
    },
  );
}
