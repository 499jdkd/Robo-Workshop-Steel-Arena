import 'dart:ui' as ui;

import 'package:flet/flet.dart';
import 'package:flet_rive/flet_rive.dart' as robot;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rive/rive.dart' as rive;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await rive.RiveNative.init();
    final font = FontLoader('Roboto')
      ..addFont(
        Future.value(
          ByteData.sublistView(
            File('C:/Windows/Fonts/segoeui.ttf').readAsBytesSync(),
          ),
        ),
      );
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(
        Future.value(
          ByteData.sublistView(
            File(
              'C:/Users/dell/flutter/3.44.8/bin/cache/artifacts/material_fonts/materialicons-regular.otf',
            ).readAsBytesSync(),
          ),
        ),
      );
    await icons.load();
  });
  for (final entry in <String, Size>{
    'portrait-small': const Size(320, 640),
    'portrait': const Size(390, 844),
    'landscape-small': const Size(640, 320),
    'landscape': const Size(844, 390),
    'desktop': const Size(1280, 720),
  }.entries) {
    testWidgets(
      '${entry.key}: real Flet adapter, Rive import and responsive arena',
      (tester) async {
        tester.view.physicalSize = entry.value;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final path = File('../assets/spark.riv').absolute;
        expect(
          path.existsSync(),
          isTrue,
          reason: 'Export the official .riv first',
        );
        final backend = FletBackend(
          pageUri: Uri.parse('http://localhost'),
          assetsDir: '',
          multiView: false,
          extensions: [robot.Extension()],
        );
        backend.pageSize = entry.value;
        backend.isLoading = false;
        final control = Control.fromMap(<String, dynamic>{
          '_c': 'RobotRive',
          '_i': 9101,
          'src': path.path,
          'expand': true,
          'arena': true,
          'action': 'attack',
          'command_id': 1,
          'renderer': 'flutter',
        }, backend);
        final key = GlobalKey();
        await tester.pumpWidget(
          ChangeNotifierProvider<FletBackend>.value(
            value: backend,
            child: MaterialApp(
              home: Scaffold(
                body: RepaintBoundary(
                  key: key,
                  child: ControlWidget(control: control),
                ),
              ),
            ),
          ),
        );
        for (
          var wait = 0;
          wait < 150 && find.byType(robot.RobotSceneView).evaluate().isEmpty;
          wait++
        ) {
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 20));
          });
          await tester.pump();
        }
        for (var i = 0; i < 60; i++) {
          await tester.pump(const Duration(milliseconds: 16));
        }
        expect(
          find.byType(robot.RobotSceneView),
          findsOneWidget,
          reason: tester.allWidgets
              .map((w) => w.runtimeType.toString())
              .join(', '),
        );
        expect(find.byType(ErrorControl), findsNothing);
        expect(tester.takeException(), isNull);
        await tester.runAsync(() async {
          final boundary =
              key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
          final image = await boundary.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final output = Directory(
            '../../../.cache/rive-research/flutter-captures',
          )..createSync(recursive: true);
          File(
            '${output.path}/${entry.key}.png',
          ).writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
        await tester.tap(find.byTooltip('Осмотреть робота'));
        await tester.pump(const Duration(milliseconds: 400));
        final view = tester.widget<robot.RobotSceneView>(
          find.byType(robot.RobotSceneView),
        );
        expect(view.painter.scene.zoomTarget, greaterThan(1));
        await tester.tap(find.byTooltip('Сбросить камеру'));
        await tester.pump(const Duration(milliseconds: 400));
        expect(view.painter.scene.zoomTarget, 1);
        expect(tester.takeException(), isNull);
        if (entry.key == 'portrait-small') {
          control.update({'src': '../assets/spark.riv'}, shouldNotify: true);
          await tester.pump();
          for (
            var wait = 0;
            wait < 150 && find.byType(robot.RobotSceneView).evaluate().isEmpty;
            wait++
          ) {
            await tester.runAsync(() async {
              await Future<void>.delayed(const Duration(milliseconds: 20));
            });
            await tester.pump();
          }
          expect(find.byType(robot.RobotSceneView), findsOneWidget);
          expect(tester.takeException(), isNull);
        }
        await tester.pumpWidget(const SizedBox.shrink());
        backend.dispose();
        await tester.pump();
        expect(tester.takeException(), isNull);
      },
    );
  }
  test(
    'published file has the eight expected animations and data binding contract',
    () async {
      final bytes = File('../assets/spark.riv').readAsBytesSync();
      final file = await rive.File.decode(
        bytes,
        riveFactory: rive.Factory.flutter,
      );
      expect(file, isNotNull);
      final board = file!.artboard('Spark')!;
      expect(board.animationCount(), 8);
      final machine = board.stateMachine('RobotMotion')!;
      final vm = file.createDefaultViewModelInstance(board)!;
      machine.bindViewModelInstance(vm);
      final mode = vm.number('mode')!;
      for (var state = 0; state < 8; state++) {
        mode.value = state.toDouble();
        for (var frame = 0; frame < 60; frame++) {
          machine.advanceAndApply(1 / 60);
        }
        expect(mode.value, state.toDouble());
      }
      final wheel = vm.number('wheelAngle')!;
      wheel.value = 1.7;
      machine.advanceAndApply(1 / 60);
      expect(wheel.value, closeTo(1.7, 1e-6));
      wheel.dispose();
      mode.dispose();
      machine.dispose();
      vm.dispose();
      board.dispose();
      file.dispose();
    },
  );
}
