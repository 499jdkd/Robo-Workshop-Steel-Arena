import 'dart:async';
import 'dart:convert';
import 'dart:ui' as ui;

import 'package:material_ui/material_ui.dart';
import 'package:flutter/scheduler.dart';

import 'profile_report.dart';

/// Optional on-device HUD. Rebuilds once a second, never once per frame.
class FrameBudgetHud extends StatefulWidget {
  const FrameBudgetHud({super.key});
  @override
  State<FrameBudgetHud> createState() => _FrameBudgetHudState();
}

class _FrameBudgetHudState extends State<FrameBudgetHud> {
  final _frames = <ui.FrameTiming>[];
  Timer? _timer;
  @override
  void initState() {
    super.initState();
    SchedulerBinding.instance.addTimingsCallback(_timings);
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {});
        if (const bool.fromEnvironment('RIVE_LOG_FPS')) {
          final first = _frames.isEmpty
              ? 0
              : _frames.first.timestampInMicroseconds(ui.FramePhase.vsyncStart);
          final last = _frames.isEmpty
              ? 0
              : _frames.last.timestampInMicroseconds(ui.FramePhase.vsyncStart);
          debugPrint(
            'RIVE_LAB_METRIC ${jsonEncode({'frames': _frames.length, 'fps': last > first ? (_frames.length - 1) * 1e6 / (last - first) : 0, 'ui_p95_ms': p95((f) => f.buildDuration.inMicroseconds), 'raster_p95_ms': p95((f) => f.rasterDuration.inMicroseconds)})}',
          );
          unawaited(
            reportProfile({
              'kind': 'frame',
              'frames': _frames.length,
              'unique_vsync_frames': _frames
                  .map(
                    (f) => f.timestampInMicroseconds(ui.FramePhase.vsyncStart),
                  )
                  .toSet()
                  .length,
              'fps': last > first
                  ? (_frames.length - 1) * 1e6 / (last - first)
                  : 0,
              'ui_p95_ms': p95((f) => f.buildDuration.inMicroseconds),
              'raster_p95_ms': p95((f) => f.rasterDuration.inMicroseconds),
              'viewport_width': MediaQuery.sizeOf(context).width,
              'viewport_height': MediaQuery.sizeOf(context).height,
            }),
          );
        }
      }
    });
  }

  void _timings(List<ui.FrameTiming> timings) {
    _frames.addAll(timings);
    if (_frames.length > 120) _frames.removeRange(0, _frames.length - 120);
  }

  @override
  void dispose() {
    _timer?.cancel();
    SchedulerBinding.instance.removeTimingsCallback(_timings);
    super.dispose();
  }

  double p95(int Function(ui.FrameTiming) read) {
    if (_frames.isEmpty) return 0;
    final samples = _frames.map(read).toList()..sort();
    return samples[((samples.length - 1) * .95).floor()] / 1000;
  }

  @override
  Widget build(BuildContext context) {
    final elapsed = _frames.length < 2
        ? 0
        : _frames.last.timestampInMicroseconds(ui.FramePhase.vsyncStart) -
              _frames.first.timestampInMicroseconds(ui.FramePhase.vsyncStart);
    final fps = elapsed <= 0
        ? '--'
        : ((_frames.length - 1) * 1e6 / elapsed).toStringAsFixed(0);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xCC0A1525),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Text(
          '$fps FPS\nUI p95 ${p95((f) => f.buildDuration.inMicroseconds).toStringAsFixed(1)} ms\nRaster p95 ${p95((f) => f.rasterDuration.inMicroseconds).toStringAsFixed(1)} ms',
          style: const TextStyle(
            color: Color(0xFFB6EFE3),
            fontSize: 11,
            fontFeatures: [ui.FontFeature.tabularFigures()],
          ),
        ),
      ),
    );
  }
}
