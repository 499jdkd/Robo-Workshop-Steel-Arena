import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flet/flet.dart';
import 'package:flet_rive/flet_rive.dart' as robot;
import 'package:rive/rive.dart' as rive;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await rive.RiveNative.init();
    final font = FontLoader('Roboto');
    font.addFont(
      Future.value(
        ByteData.sublistView(
          File('C:/Windows/Fonts/segoeui.ttf').readAsBytesSync(),
        ),
      ),
    );
    await font.load();
    final icons = FontLoader('MaterialIcons');
    icons.addFont(
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
  final fixtures = <String, Size>{
    'workshop-idle': const Size(390, 844),
    'workshop-feeding': const Size(390, 844),
    'collection': const Size(390, 844),
    'collection-boxes': const Size(390, 844),
    'reward-loading': const Size(390, 844),
    'reward-loading-large-text': const Size(320, 640),
    'reward-error': const Size(390, 844),
    'collection-boxes-small': const Size(320, 640),
    'incubator': const Size(390, 844),
    'arena-help': const Size(844, 390),
    'arena-lobby': const Size(390, 844),
    'profile-green': const Size(390, 844),
    'arena-portrait': const Size(390, 844),
    'arena-small': const Size(320, 640),
    'arena-landscape': const Size(844, 390),
    'arena-impact': const Size(844, 390),
    'arena-reply': const Size(844, 390),
    'arena-flight': const Size(844, 390),
    'workshop-landscape': const Size(844, 390),
    'workshop-landscape-siren': const Size(844, 390),
    'profile-icons': const Size(390, 844),
    'projects': const Size(390, 844),
    'supplies': const Size(390, 844),
    'robot-card-glacier': const Size(390, 650),
    'robot-card-aegis': const Size(390, 650),
    'robot-card-solar': const Size(390, 650),
    'armory':const Size(390,844),
    'armory-small':const Size(320,640),
    'online-offline':const Size(390,844),
    'online-offline-small':const Size(320,640),
    'online-active':const Size(390,844),
    'online-active-small':const Size(320,640),
    'clans-offline':const Size(390,844),
    'clans-offline-small':const Size(320,640),
    'clans-active':const Size(390,844),
    'clans-active-small':const Size(320,640),
  };
  for (final file in Directory(
    '../../.cache/ui-fixtures',
  ).listSync().whereType<File>()) {
    final name = file.uri.pathSegments.last.replaceAll('.json', '');
    if (name.startsWith('motion-')) fixtures[name] = const Size(844, 390);
  }
  for (final entry in fixtures.entries) {
    testWidgets(
      '${entry.key} renders with real Flet controls without overflow',
      (tester) async {
        tester.view.physicalSize = entry.value;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final backend = FletBackend(
          pageUri: Uri.parse('http://localhost'),
          assetsDir: '',
          multiView: false,
          extensions: [robot.Extension()],
        );
        backend.pageSize = entry.value;
        backend.isLoading = false;
        final source = jsonDecode(
          File('../../.cache/ui-fixtures/${entry.key}.json').readAsStringSync(),
        );
        final control = Control.fromMap(
          Map<String, dynamic>.from(source),
          backend,
        );
        final key = GlobalKey();
        await tester.pumpWidget(
          ChangeNotifierProvider<FletBackend>.value(
            value: backend,
            child: RepaintBoundary(
              key: key,
              child: MaterialApp(
                debugShowCheckedModeBanner: false,
                builder: (context, child) => MediaQuery(
                  data: MediaQuery.of(context).copyWith(
                    textScaler: TextScaler.linear(
                      entry.key.endsWith('large-text') ? 1.4 : 1,
                    ),
                  ),
                  child: child!,
                ),
                home: Scaffold(
                  body: ColoredBox(
                    color: const Color(0xFFF5F7FB),
                    child: ControlWidget(control: control.unwrapComponent()!),
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.runAsync(() async {
          await Future<void>.delayed(const Duration(milliseconds: 250));
        });
        final hasRive = File(
          '../../.cache/ui-fixtures/${entry.key}.json',
        ).readAsStringSync().contains('GameRive');
        if (hasRive) {
          for (
            var i = 0;
            i < 120 && find.byType(robot.GameSceneView).evaluate().isEmpty;
            i++
          ) {
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump();
          }
          expect(find.byType(robot.GameSceneView), findsWidgets);
          for (var i = 0; i < 45; i++) {
            await tester.pump(const Duration(milliseconds: 16));
          }
        } else if (entry.key.startsWith('reward-loading')) {
          // The indeterminate ring deliberately keeps scheduling animation.
          await tester.pump(const Duration(milliseconds: 400));
        } else {
          await tester.pumpAndSettle(const Duration(milliseconds: 100));
        }
        if (entry.key.startsWith('reward-loading')) {
          final cancel = find.text('Отменить загрузку');
          expect(cancel, findsOneWidget);
          await tester.ensureVisible(cancel);
          await tester.pump(const Duration(milliseconds: 500));
          final nav = find.byType(NavigationBar);
          final profileLabel = find
              .descendant(of: nav, matching: find.text('Профиль'))
              .first;
          expect(
            tester.getRect(profileLabel).bottom,
            lessThanOrEqualTo(tester.getRect(nav).bottom),
          );
          expect(
            tester.getRect(cancel).bottom,
            lessThanOrEqualTo(tester.getRect(nav).top),
          );
        }
        expect(tester.takeException(), isNull);
        expect(find.byType(ErrorControl), findsNothing);
        if (entry.key == 'arena-help') {
          expect(find.text('Как сражаться'), findsOneWidget);
        }
        final boundary =
            key.currentContext!.findRenderObject() as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image = await boundary.toImage(pixelRatio: 1.5);
          final png = await image.toByteData(format: ui.ImageByteFormat.png);
          final output = Directory('../../.cache/ui-rendered')
            ..createSync(recursive: true);
          File(
            '${output.path}/${entry.key}.png',
          ).writeAsBytesSync(png!.buffer.asUint8List());
          image.dispose();
        });
        await tester.pumpWidget(const SizedBox.shrink());
        backend.dispose();
      },
    );
  }
}
