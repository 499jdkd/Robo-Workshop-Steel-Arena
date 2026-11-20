import 'dart:async';
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';

/// Elapsed monotonic time, independent of server latency and phone wall clock.
class GameCountdown extends StatefulWidget {
  const GameCountdown({super.key, required this.control});
  final Control control;
  @override
  State<GameCountdown> createState() => _GameCountdownState();
}

class _GameCountdownState extends State<GameCountdown> {
  final watch = Stopwatch();
  Timer? timer;
  String identity = '';
  double initial = 0;
  bool emitted = false;
  int get left =>
      (initial - watch.elapsedMilliseconds / 1000).ceil().clamp(0, 8640000);
  void sync() {
    final next = widget.control.getString('countdown_id', '')!;
    if (next == identity && watch.isRunning) return;
    identity = next;
    initial = widget.control.getDouble('seconds', 0)!;
    watch
      ..reset()
      ..start();
    emitted = false;
    timer?.cancel();
    timer = Timer.periodic(const Duration(milliseconds: 250), (_) {
      if (!mounted) return;
      setState(() {});
      if (left == 0 && !emitted) {
        emitted = true;
        timer?.cancel();
        widget.control.triggerEvent('expire');
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    watch.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    sync();
    return LayoutControl(
      control: widget.control,
      child: Text(
        left == 0
            ? widget.control.getString('ready_text', 'Готово!')!
            : 'Готово через $left с',
        style: TextStyle(
          fontSize: widget.control.getDouble('size', 12),
          color: const Color(0xFF9CB4D6),
        ),
      ),
    );
  }
}
