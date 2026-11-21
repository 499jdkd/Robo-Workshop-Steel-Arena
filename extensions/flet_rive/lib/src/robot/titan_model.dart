import 'dart:collection';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:material_ui/material_ui.dart';
import 'game_motion.dart';
import 'titan_geometry.dart';

/// Native presentation of our authored Titan vector source. The geometry is
/// compiled by our own source tool, not extracted from or signed as a .riv.
/// All other characters continue to use their existing Rive artboards.
final _model = _TitanCanvasModel();

/// Caches only immutable local assemblies. Dynamic joints, gaze, glow and
/// weapon deployment remain live; each moving part retains its own transform.
/// Calling this before the first paint avoids recording assemblies in a frame.
void warmTitanModel({Color accent = const Color(0xFFFFCF64)}) {
  _model.pictures(accent);
}

/// Releases native Pictures, textures and accent materials, retaining Paths.
/// It is safe to call after a memory-pressure notification or between tests.
void clearTitanModelCaches() => _model.clearCaches();

Map<String, int> get titanModelCacheStats => {
  'sourceShapes': titanGeometryShapeCount,
  'paths': _model.paths.length,
  'materialsPerAccent': titanGeometryPaints.length,
  'accentVariants': _model.paintCache.length,
  'staticAssemblies': _model.assemblies.length,
  'staticShapes': _model.cachedShapeCount,
  'pictureAccentVariants': _model.pictureCache.length,
  'assemblyPictures': _model.pictureCache.values.fold(
    0,
    (sum, set) => sum + set.pictures.length,
  ),
  'pictureBytes': _model.pictureBytes,
  'pictureBudgetBytes': _TitanCanvasModel.pictureBudgetBytes,
  'maxAccentVariants': _TitanCanvasModel.maxAccentVariants,
  'maxAssembliesPerAccent': _TitanCanvasModel.maxAssembliesPerAccent,
  'recordedAssemblies': _model.recordedAssemblies,
  'rasterAssemblies': _model.pictureCache.values.fold(
    0,
    (sum, set) => sum + set.rasters.whereType<_TitanRaster>().length,
  ),
  'rasterBytes': _model.rasterBytes,
  'rasterBudgetBytes': _TitanCanvasModel.rasterBudgetBytes,
  'rasterizations': _model.rasterizations,
};

/// [origin] is the actual Robot root in scene coordinates, already including
/// the pose translation: (actor.center, floor + (pose.y - 126) * scale).
/// A caller can reuse one Canvas/RepaintBoundary; this does not build widgets.
void drawTitanModel(
  Canvas canvas,
  GamePose pose,
  Offset origin,
  double scale,
  double facing, {
  Color accent = const Color(0xFFFFCF64),
  Offset gaze = Offset.zero,
  bool cacheStaticAssemblies = true,
}) {
  if (!scale.isFinite ||
      scale <= 0 ||
      !origin.dx.isFinite ||
      !origin.dy.isFinite)
    return;
  _model.draw(
    canvas,
    pose,
    origin,
    scale,
    facing,
    accent,
    gaze,
    cacheStaticAssemblies: cacheStaticAssemblies,
  );
}

class _TitanMaterial {
  _TitanMaterial(this.paint, this.color, this.shader);
  final Paint paint;
  final Color color;
  final ui.Shader? shader;
  void opacity(double alpha) {
    paint.color = shader == null
        ? color.withValues(alpha: color.a * alpha)
        : const Color(0xFFFFFFFF).withValues(alpha: alpha);
  }
}

class _TitanAssembly {
  _TitanAssembly(this.roots, this.shapeCount);
  final List<int> roots;
  final int shapeCount;
  late final Rect bounds;
}

class _TitanRaster {
  _TitanRaster(this.image, this.bounds, this.bytes);
  final ui.Image image;
  final Rect bounds;
  // Reserve the largest supported pixel format plus allocation padding.
  final int bytes;
}

class _TitanDraw {
  const _TitanDraw.node(this.node) : assembly = -1;
  const _TitanDraw.assembly(this.assembly) : node = -1;
  final int node, assembly;
}

class _TitanPictures {
  _TitanPictures(this.pictures, this.rasters)
    : bytes = pictures.fold(
        0,
        (sum, picture) => sum + picture.approximateBytesUsed,
      );
  final List<ui.Picture> pictures;
  final List<_TitanRaster?> rasters;
  final int bytes;
  int get rasterBytes =>
      rasters.fold(0, (sum, raster) => sum + (raster?.bytes ?? 0));

  void dispose() {
    for (final raster in rasters) raster?.image.dispose();
    for (final picture in pictures) picture.dispose();
  }
}

class _TitanCanvasModel {
  _TitanCanvasModel() {
    _plan(0);
    for (final assembly in assemblies) {
      assembly.bounds = assembly.roots
          .map((root) => _staticBounds(root, Matrix4.identity()))
          .reduce((a, b) => a.expandToInclude(b))
          .inflate(2);
    }
  }

  static const maxAccentVariants = 8;
  static const maxAssembliesPerAccent = 64;
  static const pictureBudgetBytes = 2 * 1024 * 1024;
  static const rasterBudgetBytes = 16 * 1024 * 1024;
  static const rasterDensity = 3.0;
  final rasterPaint = Paint()..filterQuality = FilterQuality.low;
  bool rasterSupported = true;
  int rasterBytes = 0, rasterizations = 0;
  final paths = [for (final geometry in titanGeometryPaths) _path(geometry)];
  final paintCache = LinkedHashMap<int, List<_TitanMaterial>>();
  final pictureCache = LinkedHashMap<int, _TitanPictures>();
  final _uncacheableAccents = <int>{};
  final assemblies = <_TitanAssembly>[];
  final _commands = List<List<_TitanDraw>?>.filled(
    titanGeometryNodes.length,
    null,
  );
  final _static = List<bool?>.filled(titanGeometryNodes.length, null);
  final _shapeCounts = List<int?>.filled(titanGeometryNodes.length, null);
  int pictureBytes = 0, recordedAssemblies = 0;

  int get cachedShapeCount =>
      assemblies.fold(0, (sum, assembly) => sum + assembly.shapeCount);

  bool _isStatic(int index) {
    final previous = _static[index];
    if (previous != null) return previous;
    final node = titanGeometryNodes[index];
    return _static[index] =
        node.xBinding.isEmpty &&
        node.yBinding.isEmpty &&
        node.rotationBinding.isEmpty &&
        node.scaleXBinding.isEmpty &&
        node.scaleYBinding.isEmpty &&
        node.opacityBinding.isEmpty &&
        node.children.every(_isStatic);
  }

  int _shapeCount(int index) => _shapeCounts[index] ??=
      (titanGeometryNodes[index].path >= 0 ? 1 : 0) +
      titanGeometryNodes[index].children.fold(
        0,
        (sum, child) => sum + _shapeCount(child),
      );

  void _plan(int index) {
    final commands = <_TitanDraw>[], run = <int>[];
    void flush() {
      if (run.isEmpty) return;
      final shapes = run.fold(0, (sum, child) => sum + _shapeCount(child));
      // Tiny paths are cheaper to draw directly than to retain native Pictures.
      if (shapes >= 4 && assemblies.length < maxAssembliesPerAccent) {
        commands.add(_TitanDraw.assembly(assemblies.length));
        assemblies.add(_TitanAssembly(List<int>.unmodifiable(run), shapes));
      } else {
        commands.addAll(run.map(_TitanDraw.node));
      }
      run.clear();
    }

    for (final child in titanGeometryNodes[index].children) {
      if (_isStatic(child)) {
        run.add(child);
      } else {
        flush();
        commands.add(_TitanDraw.node(child));
        _plan(child);
      }
    }
    flush();
    _commands[index] = commands;
  }

  void _removePictures(int key) {
    final removed = pictureCache.remove(key);
    if (removed == null) return;
    pictureBytes -= removed.bytes;
    rasterBytes -= removed.rasterBytes;
    removed.dispose();
  }

  void clearCaches() {
    for (final set in pictureCache.values) set.dispose();
    pictureCache.clear();
    paintCache.clear();
    _uncacheableAccents.clear();
    pictureBytes = 0;
    recordedAssemblies = 0;
    rasterBytes = rasterizations = 0;
  }

  _TitanPictures? pictures(Color accent) {
    final key = accent.toARGB32();
    final paints = materials(accent);
    if (_uncacheableAccents.contains(key)) return null;
    final previous = pictureCache.remove(key);
    if (previous != null) {
      pictureCache[key] = previous;
      return previous;
    }
    final wantedRasterBytes = math.min(
      rasterBudgetBytes,
      assemblies.fold(0, (sum, a) => sum + _rasterSize(a.bounds).$3),
    );
    while (pictureCache.isNotEmpty &&
        rasterBytes + wantedRasterBytes > rasterBudgetBytes) {
      _removePictures(pictureCache.keys.first);
    }
    final result = <ui.Picture>[];
    final rasters = <_TitanRaster?>[];
    var reservedBytes = 0;
    for (final assembly in assemblies) {
      final recorder = ui.PictureRecorder();
      final canvas = Canvas(recorder);
      for (final root in assembly.roots) _staticNode(canvas, root, paints, 1);
      final picture = recorder.endRecording();
      result.add(picture);
      _TitanRaster? raster;
      final (width, height, bytes) = _rasterSize(assembly.bounds);
      if (rasterSupported &&
          width <= 1536 &&
          height <= 1536 &&
          rasterBytes + reservedBytes + bytes <= rasterBudgetBytes) {
        final wrapper = ui.PictureRecorder();
        Canvas(wrapper)
          ..scale(rasterDensity)
          ..translate(-assembly.bounds.left, -assembly.bounds.top)
          ..drawPicture(picture);
        final snapshot = wrapper.endRecording();
        try {
          raster = _TitanRaster(
            snapshot.toImageSync(width, height),
            Rect.fromLTWH(
              assembly.bounds.left,
              assembly.bounds.top,
              width / rasterDensity,
              height / rasterDensity,
            ),
            bytes,
          );
          reservedBytes += bytes;
          rasterizations++;
        } on UnsupportedError {
          rasterSupported = false;
        } finally {
          snapshot.dispose();
        }
      }
      rasters.add(raster);
      recordedAssemblies++;
    }
    final set = _TitanPictures(result, rasters);
    if (set.bytes > pictureBudgetBytes) {
      set.dispose();
      // A future oversized authoring export must not re-record and discard
      // the same Pictures every frame. Keep its vector fallback until eviction.
      _uncacheableAccents.add(key);
      return null;
    }
    while (pictureCache.isNotEmpty &&
        (pictureBytes + set.bytes > pictureBudgetBytes ||
            pictureCache.length >= maxAccentVariants)) {
      _removePictures(pictureCache.keys.first);
    }
    pictureCache[key] = set;
    pictureBytes += set.bytes;
    rasterBytes += set.rasterBytes;
    return set;
  }

  (int, int, int) _rasterSize(Rect bounds) {
    final width = math.max(1, (bounds.width * rasterDensity).ceil());
    final height = math.max(1, (bounds.height * rasterDensity).ceil());
    return (width, height, (width + 16) * (height + 16) * 16);
  }

  Rect _staticBounds(int index, Matrix4 parent) {
    final n = titanGeometryNodes[index];
    final transform = parent.clone()
      ..translateByDouble(n.x, n.y, 0, 1)
      ..rotateZ(n.rotation)
      ..scaleByDouble(n.scaleX, n.scaleY, 1, 1);
    Rect? bounds;
    if (n.path >= 0) {
      final stroke = n.paints.fold(
        0.0,
        (width, id) => math.max(width, titanGeometryPaints[id].stroke),
      );
      bounds = MatrixUtils.transformRect(
        transform,
        paths[n.path].getBounds().inflate(stroke / 2 + 1),
      );
    }
    for (final child in n.children) {
      final childBounds = _staticBounds(child, transform);
      bounds = bounds?.expandToInclude(childBounds) ?? childBounds;
    }
    return bounds ?? Rect.zero;
  }

  void _staticNode(
    Canvas canvas,
    int index,
    List<_TitanMaterial> paints,
    double inheritedAlpha,
  ) {
    final n = titanGeometryNodes[index];
    final alpha = inheritedAlpha * n.opacity.clamp(0, 1);
    if (alpha < .001 || n.scaleX.abs() < .0001 || n.scaleY.abs() < .0001)
      return;
    canvas.save();
    if (n.x != 0 || n.y != 0) canvas.translate(n.x, n.y);
    if (n.rotation != 0) canvas.rotate(n.rotation);
    if (n.scaleX != 1 || n.scaleY != 1) canvas.scale(n.scaleX, n.scaleY);
    if (n.path >= 0) {
      for (final paintId in n.paints) {
        final material = paints[paintId]..opacity(alpha);
        canvas.drawPath(paths[n.path], material.paint);
      }
    }
    for (final child in n.children) _staticNode(canvas, child, paints, alpha);
    canvas.restore();
  }

  List<_TitanMaterial> materials(Color accent) {
    final key = accent.toARGB32();
    final cached = paintCache.remove(key);
    if (cached != null) {
      paintCache[key] = cached;
      return cached;
    }
    final result = [
      for (final geometry in titanGeometryPaints) _material(geometry, accent),
    ];
    paintCache[key] = result;
    // User skins have a small finite palette; retain a bounded cache if a
    // custom theme supplies many accent colors during a long-running session.
    if (paintCache.length > maxAccentVariants) {
      final oldest = paintCache.keys.first;
      paintCache.remove(oldest);
      _uncacheableAccents.remove(oldest);
      _removePictures(oldest);
    }
    return result;
  }

  static _TitanMaterial _material(TitanGeometryPaint geometry, Color accent) {
    final colors = <Color>[
      for (var i = 0; i < geometry.colors.length; i++)
        geometry.accentStops.contains(i) ? accent : Color(geometry.colors[i]),
    ];
    final start = Offset(geometry.startX, geometry.startY);
    final end = Offset(geometry.endX, geometry.endY);
    final shader = geometry.kind == 1
        ? ui.Gradient.linear(start, end, colors, geometry.stops)
        : geometry.kind == 2
        ? ui.Gradient.radial(
            start,
            math.max(.001, (end - start).distance),
            colors,
            geometry.stops,
          )
        : null;
    final paint = Paint()
      ..isAntiAlias = true
      ..shader = shader
      ..color = geometry.kind == 0 ? colors.first : const Color(0xFFFFFFFF)
      ..style = geometry.stroke > 0 ? PaintingStyle.stroke : PaintingStyle.fill
      ..strokeWidth = geometry.stroke
      ..strokeCap = switch (geometry.cap) {
        'round' => StrokeCap.round,
        'square' => StrokeCap.square,
        _ => StrokeCap.butt,
      }
      ..strokeJoin = switch (geometry.join) {
        'round' => StrokeJoin.round,
        'bevel' => StrokeJoin.bevel,
        _ => StrokeJoin.miter,
      };
    return _TitanMaterial(paint, colors.first, shader);
  }

  static Path _path(TitanGeometryPath geometry) {
    final d = geometry.data;
    final result = Path();
    if (geometry.kind < 2) {
      final rect = Rect.fromLTWH(-d[0] * d[2], -d[1] * d[3], d[0], d[1]);
      if (geometry.kind == 0) {
        result.addOval(rect);
      } else {
        result.addRRect(
          RRect.fromRectAndCorners(
            rect,
            topLeft: Radius.circular(d[4]),
            topRight: Radius.circular(d[5]),
            bottomRight: Radius.circular(d[6]),
            bottomLeft: Radius.circular(d[7]),
          ),
        );
      }
      return result;
    }
    final count = d.length ~/ 3;
    if (count == 0) return result;
    final vertices = [
      for (var i = 0; i < count; i++) Offset(d[i * 3], d[i * 3 + 1]),
    ];
    final entries = <Offset>[], exits = <Offset>[];
    final firstControls = <Offset>[], secondControls = <Offset>[];
    for (var i = 0; i < count; i++) {
      final point = vertices[i];
      final incoming = vertices[(i - 1 + count) % count] - point;
      final outgoing = vertices[(i + 1) % count] - point;
      final radius = d[i * 3 + 2];
      if (count < 3 ||
          radius <= 0 ||
          incoming.distance < .001 ||
          outgoing.distance < .001 ||
          (!geometry.closed && (i == 0 || i == count - 1))) {
        entries.add(point);
        exits.add(point);
        firstControls.add(point);
        secondControls.add(point);
        continue;
      }
      final before = incoming / incoming.distance;
      final after = outgoing / outgoing.distance;
      final angle = math.acos(
        (before.dx * after.dx + before.dy * after.dy).clamp(-1.0, 1.0),
      );
      final tangent = math.tan(angle / 2);
      if (tangent.abs() < .001 || angle > math.pi - .001) {
        entries.add(point);
        exits.add(point);
        firstControls.add(point);
        secondControls.add(point);
        continue;
      }
      final distance = math.min(
        radius / tangent,
        math.min(incoming.distance, outgoing.distance) / 2,
      );
      final effectiveRadius = distance * tangent;
      final handle = 4 / 3 * math.tan((math.pi - angle) / 4) * effectiveRadius;
      final entry = point + before * distance, exit = point + after * distance;
      entries.add(entry);
      exits.add(exit);
      firstControls.add(entry - before * handle);
      secondControls.add(exit - after * handle);
    }
    result.moveTo(entries.first.dx, entries.first.dy);
    for (var i = 0; i < count; i++) {
      if (i > 0) result.lineTo(entries[i].dx, entries[i].dy);
      result.cubicTo(
        firstControls[i].dx,
        firstControls[i].dy,
        secondControls[i].dx,
        secondControls[i].dy,
        exits[i].dx,
        exits[i].dy,
      );
    }
    if (geometry.closed) result.close();
    return result;
  }

  double value(String binding, double fallback, GamePose pose, Offset gaze) {
    if (binding.isEmpty) return fallback;
    return switch (binding) {
      'Robot.x' => 210 + pose.x,
      'Robot.y' => 276 + pose.y,
      'Robot.rotation' => pose.rotation,
      'Head.y' => pose.headY,
      'Head.rotation' => pose.head,
      'Body.y' => pose.bodyY,
      'Body.rotation' => pose.body,
      'Arm L.rotation' => pose.armL,
      'Arm R.rotation' => pose.armR,
      'Forearm L.rotation' => pose.foreL,
      'Forearm R.rotation' => pose.foreR,
      'Eyes.scaleX' => pose.eyeX,
      'Eyes.scaleY' => pose.eyeY,
      'Smile.opacity' => pose.smile,
      'Focus mouth.opacity' => pose.focus,
      'Sad mouth.opacity' => pose.sad,
      'Brow L.rotation' => pose.brow,
      'Brow R.rotation' => -pose.brow,
      'Shield.opacity' => pose.shield,
      'Charge aura.opacity' => pose.aura,
      'lookX' => gaze.dx,
      'lookY' => gaze.dy,
      'shock' => pose.shock,
      'deploy' => math.max(.01, pose.deploy),
      'barrelY' => pose.barrel,
      'fin' => pose.fin,
      'finBack' => -pose.fin,
      'missile0' || 'missile1' => 34 - 18 * pose.deploy,
      'palm' =>
        {'shield', 'repair', 'charge', 'dodge', ''}.contains(pose.weapon)
            ? 1
            : 1 - pose.deploy,
      'plasma' ||
      'sniper' ||
      'fist' ||
      'rocket' ||
      'laser' ||
      'electric' ||
      'machinegun' ||
      'sword' ||
      'flame' ||
      'drone' ||
      'cryo' ||
      'ion' ||
      'blaster' ||
      'magnetic' ||
      'grenade' ||
      'emp' ||
      'drill' ||
      'disc' ||
      'repair' => pose.weapon == binding ? 1 : 0,
      _ => pose.extra[binding] ?? titanGeometryDefaults[binding] ?? fallback,
    };
  }

  void draw(
    Canvas canvas,
    GamePose pose,
    Offset origin,
    double scale,
    double facing,
    Color accent,
    Offset gaze, {
    bool cacheStaticAssemblies = true,
  }) {
    final paints = materials(accent);
    final recorded = cacheStaticAssemblies ? pictures(accent) : null;
    canvas.save();
    canvas.translate(origin.dx, origin.dy);
    canvas.scale(scale * (facing < 0 ? -1 : 1), scale);
    void node(int index, double inheritedAlpha) {
      final n = titanGeometryNodes[index];
      final alpha =
          inheritedAlpha *
          value(n.opacityBinding, n.opacity, pose, gaze).clamp(0, 1);
      if (alpha < .001) return;
      final sx = value(n.scaleXBinding, n.scaleX, pose, gaze);
      final sy = value(n.scaleYBinding, n.scaleY, pose, gaze);
      if (sx.abs() < .0001 || sy.abs() < .0001) return;
      canvas.save();
      if (index != 0)
        canvas.translate(
          value(n.xBinding, n.x, pose, gaze),
          value(n.yBinding, n.y, pose, gaze),
        );
      final rotation = value(n.rotationBinding, n.rotation, pose, gaze);
      if (rotation != 0) canvas.rotate(rotation);
      if (sx != 1 || sy != 1) canvas.scale(sx, sy);
      if (n.path >= 0) {
        for (final paintId in n.paints) {
          final material = paints[paintId]..opacity(alpha);
          canvas.drawPath(paths[n.path], material.paint);
        }
      }
      final commands = recorded == null ? null : _commands[index];
      if (commands == null) {
        for (final child in n.children) node(child, alpha);
      } else {
        for (final command in commands) {
          if (command.assembly < 0) {
            node(command.node, alpha);
          } else if (alpha == 1) {
            final raster = recorded!.rasters[command.assembly];
            if (raster == null) {
              canvas.drawPicture(recorded.pictures[command.assembly]);
            } else {
              canvas.drawImageRect(
                raster.image,
                Rect.fromLTWH(
                  0,
                  0,
                  raster.image.width.toDouble(),
                  raster.image.height.toDouble(),
                ),
                raster.bounds,
                rasterPaint,
              );
            }
          } else {
            // Applying group opacity to a cached composite would change how
            // overlapping translucent paths blend. Keep original per-path
            // opacity during shutdown, glow fades and all partial-alpha poses.
            for (final root in assemblies[command.assembly].roots) {
              _staticNode(canvas, root, paints, alpha);
            }
          }
        }
      }
      canvas.restore();
    }

    node(0, 1);
    canvas.restore();
  }
}
