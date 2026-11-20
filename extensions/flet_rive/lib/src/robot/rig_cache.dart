import 'dart:async';
import 'package:rive/rive.dart' as rive;

/// A reference-counted decoded rig is shared by workshop, profile and arena.
/// Artboard instances/state machines remain private to each scene.
class RigLease {
  RigLease._(this.key, this.entry);
  final String key;
  final _RigEntry entry;
  bool released = false;
  Future<rive.File?> get future => entry.future;
  void release() {
    if (released) return;
    released = true;
    entry.references--;
    if (entry.references == 0)
      entry.expiry = Timer(const Duration(seconds: 30), () async {
        if (entry.references != 0) return;
        _entries.remove(key);
        try {
          (await entry.future)?.dispose();
        } catch (_) {}
      });
  }
}

class _RigEntry {
  _RigEntry(this.future);
  final Future<rive.File?> future;
  int references = 0;
  Timer? expiry;
}

final _entries = <String, _RigEntry>{};
RigLease acquireRig(String key, Future<rive.File?> Function() loader) {
  final entry = _entries.putIfAbsent(key, () => _RigEntry(loader()));
  entry.expiry?.cancel();
  entry.expiry = null;
  entry.references++;
  return RigLease._(key, entry);
}

/// Release idle entries immediately on memory pressure or after a test scene.
Future<void> clearIdleRigCache() async {
  for (final key in _entries.keys.toList()) {
    final entry = _entries[key]!;
    if (entry.references != 0) continue;
    entry.expiry?.cancel();
    _entries.remove(key);
    try {
      (await entry.future)?.dispose();
    } catch (_) {}
  }
}
