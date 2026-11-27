import 'dart:io' as io;
import 'dart:ui' as ui;
import 'package:flet_rive/flet_rive.dart';
import 'package:flet_rive/src/robot/robot_profiles.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rive/rive.dart' as rive;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late rive.File file;
  setUpAll(() async {
    await rive.RiveNative.init();
    file = (await rive.File.path(io.File('../../src/assets/animation/game_robot.riv').absolute.path,
        riveFactory: rive.Factory.flutter))!;
  });
  tearDownAll(() => file.dispose());
  for (final id in robotProfiles.keys) {
    for (final ultimate in [true, false]) {
    testWidgets('$id ${ultimate ? 'super' : 'skill'} uses the real rig and returns from its demonstration', (tester) async {
      tester.view.physicalSize = const Size(640, 360);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final painter = GameScenePainter(file);
      final scene = painter.scene..viewport = const Size(640, 360);
      scene.update({'arena':false,'demonstration':true,'expanded':true,'robot':id,
        'mobility':robotProfiles[id]!['mobility'],'accent':'#78DCFF','sound':false,
        'action':'special','combatAction':ultimate ? 'ultimate' : 'special','phase':'workshop','event':'demo-$id'});
      final key = GlobalKey();
      await tester.pumpWidget(MaterialApp(home: Scaffold(backgroundColor: const Color(0xFF10233F),
        body: RepaintBoundary(key:key, child: GameSceneView(file:file,painter:painter)))));
      for (var i = 0; i < 55; i++) await tester.pump(const Duration(milliseconds:16));
      expect(scene.signatureVisible, isTrue);
      expect(tester.takeException(), isNull);
      final boundary = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
      await tester.runAsync(() async {
        final frame = await boundary.toImage(pixelRatio:1.5);
        final bytes = await frame.toByteData(format:ui.ImageByteFormat.png);
        final out = io.Directory('../../.cache/interaction-v27/signatures')..createSync(recursive:true);
        io.File('${out.path}/$id${ultimate ? '' : '-skill'}.png').writeAsBytesSync(bytes!.buffer.asUint8List());
        frame.dispose();
      });
      final recoveryFrames = id == 'titan' && ultimate ? 170 : 110;
      for (var i = 0; i < recoveryFrames; i++) await tester.pump(const Duration(milliseconds:16));
      expect(scene.signatureVisible, isFalse);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      painter.dispose();
    });
    }
  }
  testWidgets('floor and long press do not invoke the workshop reward callback', (tester) async {
    tester.view.physicalSize = const Size(640, 360);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final painter = GameScenePainter(file);
    painter.scene..viewport = const Size(640,360)..update({'arena':false,'robot':'volt','mobility':'hover','sound':false,'event':'0'});
    var rewards = 0;
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:GameSceneView(file:file,painter:painter,onRobotTap:()=>rewards++))));
    await tester.pump(const Duration(milliseconds:16));
    await tester.tapAt(const Offset(580,300));
    expect(rewards, 0);
    expect(painter.scene.manualPosition, isTrue);
    await tester.pump(const Duration(milliseconds:16));
    final target = painter.scene.target(painter.scene.player);
    await tester.longPressAt(target);
    expect(rewards, 0);
    await tester.tapAt(painter.scene.target(painter.scene.player));
    expect(rewards, 1);
    await tester.pumpWidget(const SizedBox.shrink());
    painter.dispose();
  });
}
