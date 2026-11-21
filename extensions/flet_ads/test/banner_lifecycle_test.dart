import 'package:flet/flet.dart';
import 'package:flet_ads/src/banner.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
// The SDK exposes this manager to its own method-channel tests as well.
// ignore: implementation_imports
import 'package:google_mobile_ads/src/ad_instance_manager.dart';

class RecordingBackend implements FletBackend {
  final events = <String>[];

  @override
  void triggerControlEvent(Control control, String name, [dynamic data]) {
    events.add(name);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('banner configures privacy, survives rebuilds, and disposes ads',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);
    final calls = <MethodCall>[];
    var failInitialConfiguration = true;
    instanceManager = AdInstanceManager('plugins.flutter.io/google_mobile_ads');
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(instanceManager.channel, (call) async {
      calls.add(call);
      if (call.method == 'MobileAds#updateRequestConfiguration' &&
          failInitialConfiguration) {
        failInitialConfiguration = false;
        throw PlatformException(code: 'temporary-network-failure');
      }
      if (call.method == 'MobileAds#initialize')
        return InitializationStatus({});
      if (call.method == 'getAdSize') return AdSize.banner;
      return null;
    });
    messenger.setMockMethodCallHandler(SystemChannels.platform_views,
        (call) async {
      if (call.method == 'create') return 0;
      if (call.method == 'resize') return {'width': 320.0, 'height': 50.0};
      return null;
    });
    addTearDown(() {
      messenger.setMockMethodCallHandler(instanceManager.channel, null);
      messenger.setMockMethodCallHandler(SystemChannels.platform_views, null);
    });

    final backend = RecordingBackend();
    final control = Control(
      id: 10,
      type: 'BannerAd',
      properties: {
        'unit_id': 'first-test-unit',
        'width': 320.0,
        'height': 50.0,
        'request': {'non_personalized_ads': true},
      },
      backend: backend,
    );
    Widget host(String screen) => MaterialApp(
          home: Column(children: [
            Text(screen),
            BannerAdControl(key: const ValueKey('footer'), control: control),
          ]),
        );

    await tester.pumpWidget(host('Initial failure'));
    await tester.pump();
    expect(backend.events, contains('error'));
    expect(calls.where((call) => call.method == 'loadBannerAd'), isEmpty);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    calls.clear();
    backend.events.clear();
    await tester.pumpWidget(host('Home'));
    await tester.pump();
    final configurationIndex = calls.indexWhere(
        (call) => call.method == 'MobileAds#updateRequestConfiguration');
    final initializationIndex =
        calls.indexWhere((call) => call.method == 'MobileAds#initialize');
    final loadIndex = calls.indexWhere((call) => call.method == 'loadBannerAd');
    expect(configurationIndex, greaterThanOrEqualTo(0));
    expect(initializationIndex, greaterThan(configurationIndex));
    expect(loadIndex, greaterThan(initializationIndex));
    final settings = calls[configurationIndex].arguments as Map;
    expect(
        settings['ageRestrictedTreatment'], AgeRestrictedTreatment.child.index);
    expect(settings['maxAdContentRating'], MaxAdContentRating.g);
    final firstLoad = calls.firstWhere((call) => call.method == 'loadBannerAd');
    final firstId = firstLoad.arguments['adId'] as int;
    final firstAd = instanceManager.adFor(firstId) as BannerAd;
    expect(firstAd.request.nonPersonalizedAds, isTrue);
    expect(find.byType(AdWidget), findsNothing);

    firstAd.listener.onAdLoaded!(firstAd);
    await tester.pump();
    expect(find.byType(AdWidget), findsOneWidget);
    await tester.pumpWidget(host('Shop'));
    await tester.pump();
    expect(calls.where((call) => call.method == 'loadBannerAd').length, 1);
    expect(instanceManager.adFor(firstId), same(firstAd));

    control.properties['unit_id'] = 'second-test-unit';
    await tester.pumpWidget(host('Profile'));
    await tester.pump();
    expect(calls.where((call) => call.method == 'loadBannerAd').length, 2);
    expect(calls.where((call) => call.method == 'disposeAd').length, 1);
    final secondLoad = calls.lastWhere((call) => call.method == 'loadBannerAd');
    final secondId = secondLoad.arguments['adId'] as int;
    final secondAd = instanceManager.adFor(secondId) as BannerAd;
    firstAd.listener.onAdLoaded!(firstAd);
    await tester.pump();
    expect(find.byType(AdWidget), findsNothing);
    secondAd.listener.onAdLoaded!(secondAd);
    await tester.pump();
    expect(find.byType(AdWidget), findsOneWidget);

    final replacement = Control(
        id: 11,
        type: 'BannerAd',
        properties: Map<String, dynamic>.from(control.properties),
        backend: backend);
    await tester.pumpWidget(MaterialApp(
        home: Column(children: [
      BannerAdControl(key: const ValueKey('footer'), control: replacement),
    ])));
    await tester.pump();
    expect(calls.where((call) => call.method == 'loadBannerAd').length, 3);
    final thirdId = calls
        .lastWhere((call) => call.method == 'loadBannerAd')
        .arguments['adId'] as int;
    final thirdAd = instanceManager.adFor(thirdId) as BannerAd;
    thirdAd.listener.onAdLoaded!(thirdAd);
    await tester.pump();
    expect(find.byType(AdWidget), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    expect(calls.where((call) => call.method == 'disposeAd').length, 3);
    expect(instanceManager.adFor(secondId), isNull);
    secondAd.listener.onAdLoaded!(secondAd);
    await tester.pump();
    expect(tester.takeException(), isNull);
    debugDefaultTargetPlatformOverride = null;
  });
}
