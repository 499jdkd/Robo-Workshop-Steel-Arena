# Clicker changes to Flet Ads 1.0.4

Upstream: https://github.com/flet-dev/flet/tree/v1.0.4/sdk/python/packages/flet-ads

The Dart files were copied from the official `flet-ads==1.0.4` Python wheel.
Their Apache 2.0 license is retained in LICENSE.

Local changes, 2026-11-13:

- Keep one BannerAd per widget and dispose it when removed. The upstream widget
  constructs a new ad in build(), including the rebuild after onAdLoaded.
- Render AdWidget only once its ad has loaded.
- Delay Google Mobile Ads initialization until the Python layer permits a
  Google demo request or an owner request authorized by UMP.
- Before initialization, apply child-directed treatment and maximum content
  rating G. All users are treated as children/unknown age; no age is collected.
- Use a portable Flet dependency instead of the upstream monorepo path.
- Pin Google Mobile Ads 9.2.0 and use its current AgeRestrictedTreatment API.

The Python API remains the official flet-ads 1.0.4 package. The Flutter dependency
override in pyproject.toml selects this local Dart implementation for builds.
This project uses only the banner and consent services, not interstitial ads.

Recovery changes, 2026-11-14:

- Clear a failed SDK initialization Future so a later request can retry.
- Reload when the Flet control ID changes, including a new request with the
  same ad unit; forward the widget key supplied by Flet.
- Extend the native test with a transient initialization failure and same-unit
  replacement. Child treatment, content rating G and NPA remain unchanged.
