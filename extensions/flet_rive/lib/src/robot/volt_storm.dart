/// One clock for the ultimate's gathering, compression and release. The
/// arena's existing release (.62) and hit (.90) boundaries stay unchanged.
class VoltStorm {
  VoltStorm(double time) : t = time.isFinite ? time.clamp(0.0, 1.0) : 0;
  final double t;
  static const maximumRadius = 86.0;
  static const boundsRadius = 124.0;
  static double _ramp(double value, double from, double to) {
    final p = ((value - from) / (to - from)).clamp(0.0, 1.0);
    return p * p * (3 - 2 * p);
  }

  double get growth => _ramp(t, .10, .52);
  double get pressure => _ramp(t, .52, .62) * (1 - _ramp(t, .62, .72));
  double get charge => growth * (1 - _ramp(t, .62, .78));
  double get radius => 7 + 79 * growth - 14 * pressure;
  double get discharge => _ramp(t, .62, .67) * (1 - _ramp(t, .91, 1));
  double get extension => _ramp(t, .62, .72);
  double get ignition => _ramp(t, .62, .66) * (1 - _ramp(t, .67, .78));
  double get arrival => _ramp(t, .86, .90) * (1 - _ramp(t, .93, 1));
}
