import 'dart:collection';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'game_motion.dart';
import 'volt_geometry.dart';

/// Native presentation of our authored Volt vector source. The geometry is
/// compiled by our own source tool, not extracted from or signed as a .riv.
/// All other characters continue to use their existing Rive artboards.
final _model = _VoltCanvasModel();

void warmVoltModel({Color accent = const Color(0xFF36DFFF)}) =>
    _model.materials(accent);

Map<String, int> get voltModelCacheStats => {
  'sourceShapes': voltGeometryShapeCount,
  'paths': _model.paths.length,
  'materialsPerAccent': voltGeometryPaints.length,
  'accentVariants': _model.paintCache.length,
};

/// [origin] is the actual Robot root in scene coordinates, already including
/// the pose translation: (actor.center, floor + (pose.y - 126) * scale).
/// A caller can reuse one Canvas/RepaintBoundary; this does not build widgets.
void drawVoltModel(
  Canvas canvas,
  GamePose pose,
  Offset origin,
  double scale,
  double facing, {
  Color accent = const Color(0xFF36DFFF),
  Offset gaze = Offset.zero,
}) {
  if (!scale.isFinite ||
      scale <= 0 ||
      !origin.dx.isFinite ||
      !origin.dy.isFinite)
    return;
  _model.draw(canvas, pose, origin, scale, facing, accent, gaze);
}

class _VoltMaterial {
  _VoltMaterial(this.paint, this.color, this.shader);
  final Paint paint;
  final Color color;
  final ui.Shader? shader;
  void opacity(double alpha) {
    paint.color = shader == null
        ? color.withValues(alpha: color.a * alpha)
        : const Color(0xFFFFFFFF).withValues(alpha: alpha);
  }
}

class _VoltCanvasModel {
  final paths = [for (final geometry in voltGeometryPaths) _path(geometry)];
  final paintCache = LinkedHashMap<int, List<_VoltMaterial>>();

  List<_VoltMaterial> materials(Color accent) {
    final key = accent.toARGB32();
    final cached = paintCache.remove(key);
    if (cached != null) {
      paintCache[key] = cached;
      return cached;
    }
    final result = [
      for (final geometry in voltGeometryPaints) _material(geometry, accent),
    ];
    paintCache[key] = result;
    // User skins have a small finite palette; retain a bounded cache if a
    // custom theme supplies many accent colors during a long-running session.
    if (paintCache.length > 8) paintCache.remove(paintCache.keys.first);
    return result;
  }

  static _VoltMaterial _material(VoltGeometryPaint geometry, Color accent) {
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
    return _VoltMaterial(paint, colors.first, shader);
  }

  static Path _path(VoltGeometryPath geometry) {
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
      _ => pose.extra[binding] ?? voltGeometryDefaults[binding] ?? fallback,
    };
  }

  void draw(
    Canvas canvas,
    GamePose pose,
    Offset origin,
    double scale,
    double facing,
    Color accent,
    Offset gaze,
  ) {
    final paints = materials(accent);
    canvas.save();
    canvas.translate(origin.dx, origin.dy);
    canvas.scale(scale * (facing < 0 ? -1 : 1), scale);
    void node(int index, double inheritedAlpha) {
      final n = voltGeometryNodes[index];
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
      for (final child in n.children) node(child, alpha);
      canvas.restore();
    }

    node(0, 1);
    canvas.restore();
  }
}
