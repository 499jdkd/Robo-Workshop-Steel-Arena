import 'dart:async';

import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

import '../utils/ads.dart';

class BannerAdControl extends StatefulWidget {
  final Control control;

  const BannerAdControl({super.key, required this.control});

  @override
  State<BannerAdControl> createState() => _BannerAdControlState();
}

class _BannerAdControlState extends State<BannerAdControl> with FletStoreMixin {
  BannerAd? _banner;
  bool _isLoaded = false;
  int _generation = 0;
  late String _unitId;
  late int _controlId;

  String get _requestedUnitId => widget.control.getString('unit_id')!;

  @override
  void initState() {
    super.initState();
    _unitId = _requestedUnitId;
    _controlId = widget.control.id;
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant BannerAdControl oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_unitId != _requestedUnitId || _controlId != widget.control.id) {
      _unitId = _requestedUnitId;
      _controlId = widget.control.id;
      _banner?.dispose();
      _banner = null;
      _isLoaded = false;
      unawaited(_load());
    }
  }

  bool _isCurrent(Ad ad, int generation) =>
      mounted && generation == _generation && identical(ad, _banner);

  void _emit(Ad ad, int generation, String name) {
    if (_isCurrent(ad, generation)) widget.control.triggerEvent(name);
  }

  Future<void> _load() async {
    final generation = ++_generation;
    try {
      // Google demo inventory or a publisher unit authorized by Python's UMP gate.
      await initializeChildSafeAds();
      if (!mounted || generation != _generation) return;

      final banner = BannerAd(
        adUnitId: _unitId,
        request: parseAdRequest(widget.control.get('request'),
            const AdRequest(nonPersonalizedAds: true))!,
        size: AdSize.banner,
        listener: BannerAdListener(
          onAdLoaded: (ad) {
            if (!_isCurrent(ad, generation)) {
              ad.dispose();
              return;
            }
            setState(() => _isLoaded = true);
            widget.control.triggerEvent('load');
          },
          onAdFailedToLoad: (ad, error) {
            final current = _isCurrent(ad, generation);
            ad.dispose();
            if (current) {
              setState(() {
                _banner = null;
                _isLoaded = false;
              });
              widget.control.triggerEvent('error', error.toString());
            }
          },
          onAdOpened: (ad) => _emit(ad, generation, 'open'),
          onAdClosed: (ad) => _emit(ad, generation, 'close'),
          onAdClicked: (ad) => _emit(ad, generation, 'click'),
          onAdWillDismissScreen: (ad) => _emit(ad, generation, 'will_dismiss'),
          onAdImpression: (ad) => _emit(ad, generation, 'impression'),
          onPaidEvent: (ad, valueMicros, precision, currencyCode) {
            if (_isCurrent(ad, generation)) {
              widget.control.triggerEvent('paid', {
                'value': valueMicros,
                'precision': precision.name,
                'currency_code': currencyCode,
              });
            }
          },
        ),
      );
      _banner = banner;
      await banner.load();
    } catch (error) {
      if (mounted && generation == _generation) {
        _banner?.dispose();
        setState(() {
          _banner = null;
          _isLoaded = false;
        });
        widget.control.triggerEvent('error', error.toString());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final banner = _banner;
    return LayoutControl(
      control: widget.control,
      child: SizedBox(
        width: AdSize.banner.width.toDouble(),
        height: AdSize.banner.height.toDouble(),
        child: _isLoaded && banner != null ? AdWidget(ad: banner) : null,
      ),
    );
  }

  @override
  void dispose() {
    ++_generation;
    _banner?.dispose();
    _banner = null;
    super.dispose();
  }
}
