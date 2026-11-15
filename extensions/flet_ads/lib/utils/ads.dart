import 'package:google_mobile_ads/google_mobile_ads.dart';

Future<void>? _initialization;

/// Unknown-age users receive child-directed, G-rated ad requests.
/// Apply the restrictions before SDK initialization or any ad load.
Future<void> initializeChildSafeAds() async {
  final pending = _initialization ??= _configureChildSafeAds();
  try {
    await pending;
  } catch (_) {
    if (identical(_initialization, pending)) _initialization = null;
    rethrow;
  }
}

Future<void> _configureChildSafeAds() async {
  await MobileAds.instance.updateRequestConfiguration(RequestConfiguration(
    ageRestrictedTreatment: AgeRestrictedTreatment.child,
    maxAdContentRating: MaxAdContentRating.g,
  ));
  await MobileAds.instance.initialize();
}

AdRequest? parseAdRequest(dynamic value, [AdRequest? defaultValue]) {
  if (value == null) return defaultValue;

  return AdRequest(
    keywords: value["keywords"],
    contentUrl: value["content_url"],
    nonPersonalizedAds: value["non_personalized_ads"],
    neighboringContentUrls: value["neighboring_content_urls"],
    httpTimeoutMillis: value["http_timeout"],
    extras: value["extras"],
  );
}
