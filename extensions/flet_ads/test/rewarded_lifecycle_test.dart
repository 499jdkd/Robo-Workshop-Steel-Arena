import 'package:flet/flet.dart';
import 'package:flet_ads/src/rewarded.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
// The SDK exposes this manager to its own method-channel tests as well.
// ignore: implementation_imports
import 'package:google_mobile_ads/src/ad_instance_manager.dart';

class RewardBackend implements FletBackend {
  final events = <Map<String, dynamic>>[];
  @override
  void triggerControlEvent(Control control, String name, [dynamic data]) {
    events.add({'name': name, 'data': data});
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('earned callback grants once; cancelled and old ads never grant',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);
    final calls = <MethodCall>[];
    instanceManager = AdInstanceManager('plugins.flutter.io/google_mobile_ads');
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(instanceManager.channel, (call) async {
      calls.add(call);
      if (call.method == 'MobileAds#initialize')
        return InitializationStatus({});
      return null;
    });
    addTearDown(() =>
        messenger.setMockMethodCallHandler(instanceManager.channel, null));
    final backend = RewardBackend();
    final control = Control(
        id: 101,
        type: 'RewardedAd',
        properties: {
          'unit_id': 'ca-app-pub-3940256099942544/5224354917',
          'request': {'non_personalized_ads': true},
        },
        backend: backend);
    final service = RewardedAdService(control: control)..init();
    await service.load('first');
    final configuration = calls.indexWhere(
        (call) => call.method == 'MobileAds#updateRequestConfiguration');
    final loadIndex =
        calls.indexWhere((call) => call.method == 'loadRewardedAd');
    expect(configuration, greaterThanOrEqualTo(0));
    expect(loadIndex, greaterThan(configuration));
    expect(calls[configuration].arguments['ageRestrictedTreatment'],
        AgeRestrictedTreatment.child.index);
    expect(calls[configuration].arguments['maxAdContentRating'],
        MaxAdContentRating.g);
    final firstId = calls[loadIndex].arguments['adId'] as int;
    final first = instanceManager.adFor(firstId) as RewardedAd;
    expect(first.request!.nonPersonalizedAds, isTrue);
    first.rewardedAdLoadCallback.onAdLoaded(first);
    await service.show('first');
    expect(backend.events.where((event) => event['name'] == 'reward'), isEmpty);
    first.onUserEarnedRewardCallback!(first, RewardItem(1, 'reward'));
    first.onUserEarnedRewardCallback!(first, RewardItem(1, 'reward'));
    expect(
        backend.events.where((event) => event['name'] == 'reward').length, 1);
    expect(
        backend.events.firstWhere((event) => event['name'] == 'reward')['data']
            ['request_id'],
        'first');
    first.fullScreenContentCallback!.onAdDismissedFullScreenContent!(first);
    await service.load('cancelled');
    final secondCall =
        calls.lastWhere((call) => call.method == 'loadRewardedAd');
    final second = instanceManager.adFor(secondCall.arguments['adId'] as int)
        as RewardedAd;
    service.cancel();
    second.rewardedAdLoadCallback.onAdLoaded(second);
    expect(
        backend.events.where((event) =>
            event['name'] == 'load' &&
            event['data']['request_id'] == 'cancelled'),
        isEmpty);
    first.onUserEarnedRewardCallback!(first, RewardItem(1, 'reward'));
    expect(
        backend.events.where((event) => event['name'] == 'reward').length, 1);
    await service.load('failed');
    final failedCall =
        calls.lastWhere((call) => call.method == 'loadRewardedAd');
    final failedAd = instanceManager.adFor(failedCall.arguments['adId'] as int)
        as RewardedAd;
    failedAd.rewardedAdLoadCallback.onAdFailedToLoad(
        LoadAdError(3, 'com.google.android.gms.ads', 'No fill', null));
    final failure = backend.events.last;
    expect(failure['name'], 'error');
    expect(failure['data']['request_id'], 'failed');
    expect(failure['data']['stage'], 'load');
    expect(failure['data']['code'], 3);
    expect(failure['data']['domain'], 'com.google.android.gms.ads');
    expect(failure['data']['message'], 'No fill');
    service.dispose();
    debugDefaultTargetPlatformOverride = null;
  });
}
