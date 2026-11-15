import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clicker_rive_lab/frame_budget.dart';

void main() {
  testWidgets('FPS HUD releases its timer and timing subscription', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: FrameBudgetHud()));
    await tester.pump(const Duration(seconds: 2));
    expect(find.textContaining('FPS'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 2));
    expect(tester.takeException(), isNull);
  });
}
