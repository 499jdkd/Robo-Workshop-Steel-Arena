import 'package:flet/flet.dart';
import 'package:flet_rive/flet_rive.dart' as robot;
import 'package:material_ui/material_ui.dart';
import 'frame_budget.dart';
import 'profile_report.dart';

Future<void> startGame() async {
  WidgetsFlutterBinding.ensureInitialized();
  const configuredServer = String.fromEnvironment('CLICKER_SERVER');
  final server =
      Uri.base.queryParameters['server'] ??
      (configuredServer.isNotEmpty ? configuredServer : Uri.base.origin);
  if (const bool.fromEnvironment('RIVE_LOG_FPS')) {
    final previous = FlutterError.onError;
    FlutterError.onError = (details) {
      previous?.call(details);
      reportProfile({
        'kind': 'flutter-error',
        'message': details.exceptionAsString(),
        'stack': details.stack.toString(),
      });
    };
  }
  runApp(
    MediaQuery.fromView(
      view: WidgetsBinding.instance.platformDispatcher.implicitView!,
      child: Directionality(
        textDirection: TextDirection.ltr,
        child: Stack(
          textDirection: TextDirection.ltr,
          children: [
            FletApp(
              pageUrl: server,
              assetsDir: '$server/',
              extensions: [robot.Extension()],
            ),
            if (const bool.fromEnvironment('RIVE_START_FPS'))
              const Positioned(
                top: 4,
                right: 4,
                child: Material(child: FrameBudgetHud()),
              ),
          ],
        ),
      ),
    ),
  );
}
