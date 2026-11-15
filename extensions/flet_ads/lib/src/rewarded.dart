import 'package:flet/flet.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

import '../utils/ads.dart';

/// One reusable service; every load and callback belongs to a request token.
class RewardedAdService extends FletService {
  RewardedAdService({required super.control});

  RewardedAd? _ad;
  int _generation = 0;
  bool _disposed = false;
  bool _shown = false;
  bool _earned = false;
  String _requestId = '';

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  void _event(String name, String token,
      [Map<String, dynamic> extra = const {}]) {
    if (!_disposed) control.triggerEvent(name, {'request_id': token, ...extra});
  }

  Future<void> load(String token) async {
    if (_disposed || _shown) return;
    final generation = ++_generation;
    _ad?.dispose();
    _ad = null;
    _requestId = token;
    _earned = false;
    try {
      await initializeChildSafeAds();
      if (_disposed || generation != _generation) return;
      await RewardedAd.load(
        adUnitId: control.getString('unit_id')!,
        request: parseAdRequest(
            control.get('request'), const AdRequest(nonPersonalizedAds: true))!,
        rewardedAdLoadCallback: RewardedAdLoadCallback(
          onAdLoaded: (ad) {
            if (_disposed || generation != _generation) {
              ad.dispose();
              return;
            }
            _ad = ad;
            ad.fullScreenContentCallback = FullScreenContentCallback(
              onAdShowedFullScreenContent: (_) => _event('open', token),
              onAdDismissedFullScreenContent: (_) {
                if (generation != _generation) return;
                _shown = false;
                _ad = null;
                ad.dispose();
                _event('close', token);
              },
              onAdFailedToShowFullScreenContent: (_, error) {
                if (generation != _generation) return;
                _shown = false;
                _ad = null;
                ad.dispose();
                _event('error', token, {
                  'stage': 'show',
                  'code': error.code,
                  'domain': error.domain,
                  'message': error.message,
                });
              },
            );
            _event('load', token);
          },
          onAdFailedToLoad: (error) {
            if (!_disposed && generation == _generation) {
              _event('error', token, {
                'stage': 'load',
                'code': error.code,
                'domain': error.domain,
                'message': error.message,
                'response_info': error.responseInfo?.toString(),
              });
            }
          },
        ),
      );
    } catch (error) {
      if (!_disposed && generation == _generation) {
        _event('error', token,
            {'stage': 'initialize', 'message': error.toString()});
      }
    }
  }

  Future<void> show(String token) async {
    final ad = _ad;
    if (_disposed || _shown || ad == null || token != _requestId) {
      throw StateError('Rewarded video is not ready for this request');
    }
    _shown = true;
    final generation = _generation;
    try {
      await ad.show(onUserEarnedReward: (_, reward) {
        if (_disposed || generation != _generation || _earned) return;
        _earned = true;
        _event('reward', token, {'amount': reward.amount, 'type': reward.type});
      });
    } catch (error) {
      _shown = false;
      _ad = null;
      ad.dispose();
      _event('error', token, {'stage': 'show', 'message': error.toString()});
    }
  }

  void cancel() {
    if (_shown) return; // A displayed SDK ad is closed by the user.
    ++_generation;
    _ad?.dispose();
    _ad = null;
    _requestId = '';
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    switch (name) {
      case 'load':
        return load(args['request_id'] as String);
      case 'show':
        return show(args['request_id'] as String);
      case 'cancel':
        cancel();
        return null;
      case 'dispose':
        dispose();
        return null;
      default:
        throw ArgumentError('Unknown rewarded method: $name');
    }
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    ++_generation;
    _ad?.dispose();
    _ad = null;
    super.dispose();
  }
}
