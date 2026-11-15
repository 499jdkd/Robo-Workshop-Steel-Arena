import 'package:flet/flet.dart';
import 'package:flutter/cupertino.dart';

import 'banner.dart';
import 'consent_manager.dart';
import 'interstitial.dart';
import 'rewarded.dart';

class Extension extends FletExtension {
  // The banner applies child/G restrictions before initializing Mobile Ads.

  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "InterstitialAd":
        return InterstitialAdService(control: control);
      case "ConsentManager":
        return ConsentManagerService(control: control);
      case "RewardedAd":
        return RewardedAdService(control: control);
      default:
        return null;
    }
  }

  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "BannerAd":
        return BannerAdControl(key: key, control: control);
      /* TODO: Finalize NativeAdControl -> https://developers.google.com/admob/flutter/native/platforms
      case "NativeAd":
        return NativeAdControl(control: control);
      */
      default:
        return null;
    }
  }
}
