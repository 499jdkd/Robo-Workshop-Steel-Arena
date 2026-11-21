import 'dart:convert';
import 'dart:io';

import 'package:flet/flet.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

Map<String, dynamic> shell(String name) => Map<String, dynamic>.from(
  jsonDecode(
    File(
      '${Platform.environment['VOLT_ROUTE_FIXTURES'] ?? '../../.cache/volt-refinement/qa/route-fixtures'}/$name.json',
    ).readAsStringSync(),
  ),
);

void main() {
  testWidgets('main route shell removes outgoing screens on the next frame', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final backend = FletBackend(
      pageUri: Uri.parse('http://localhost'),
      assetsDir: '',
      multiView: false,
      extensions: [],
    );
    backend.pageSize = const Size(390, 844);
    backend.isLoading = false;
    final root = Control.fromMap(shell('route-profile'), backend);
    await tester.pumpWidget(
      ChangeNotifierProvider<FletBackend>.value(
        value: backend,
        child: MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(body: ControlWidget(control: root)),
        ),
      ),
    );
    await tester.pump();
    var current = 'route-profile';
    expect(find.text(current), findsOneWidget);
    for (final next in [
      'route-workshop',
      'route-collection',
      'route-workshop',
      'route-arena',
      'route-profile',
    ]) {
      root.update(shell(next), shouldNotify: true);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 16));
      expect(find.text(next), findsOneWidget);
      expect(
        find.text(current),
        findsNothing,
        reason:
            'The outgoing $current must not linger over $next while fading out',
      );
      for (final label in [
        'route-profile',
        'route-workshop',
        'route-collection',
        'route-arena',
      ]) {
        if (label != next) expect(find.text(label), findsNothing);
      }
      expect(tester.takeException(), isNull);
      current = next;
    }
    await tester.pumpWidget(const SizedBox.shrink());
    backend.dispose();
  });
}
