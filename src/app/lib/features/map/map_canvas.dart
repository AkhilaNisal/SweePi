import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../../core/models/robot_models.dart';
import '../app/app_controller.dart';

class MapCanvas extends StatefulWidget {
  const MapCanvas({
    super.key,
    required this.mapData,
    required this.selection,
    required this.onSelectionChanged,
    this.robotPose,
    this.sections = const [],
    this.selectedSectionIds = const {},
    this.onSectionTap,
    this.selectionEnabled = true,
  });

  final SweePiMapData mapData;
  final RectSelection? selection;
  final ValueChanged<RectSelection?> onSelectionChanged;
  final RobotPose? robotPose;
  final List<MapSection> sections;
  final Set<String> selectedSectionIds;
  final ValueChanged<MapSection?>? onSectionTap;
  final bool selectionEnabled;

  @override
  State<MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<MapCanvas> {
  ui.Image? _raster;

  @override
  void initState() {
    super.initState();
    _rebuildRaster();
  }

  @override
  void didUpdateWidget(covariant MapCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.mapData.mapId != widget.mapData.mapId ||
        oldWidget.mapData.occupancy.length != widget.mapData.occupancy.length) {
      _rebuildRaster();
    }
  }

  Future<void> _rebuildRaster() async {
    if (!widget.mapData.available) {
      setState(() => _raster = null);
      return;
    }

    final width = widget.mapData.width;
    final height = widget.mapData.height;
    final rgba = Uint8List(width * height * 4);

    for (var mapY = 0; mapY < height; mapY++) {
      for (var mapX = 0; mapX < width; mapX++) {
        final sourceIndex = mapY * width + mapX;
        final targetY = height - 1 - mapY;
        final targetIndex = (targetY * width + mapX) * 4;
        final occupancy = widget.mapData.occupancy[sourceIndex];

        final color = switch (occupancy) {
          < 0 => const Color(0xFFC9D1D0),
          0 => const Color(0xFFF8FCF6),
          >= 65 => const Color(0xFF25302B),
          _ => const Color(0xFFE0E8E3),
        };

        rgba[targetIndex] = (color.r * 255).round().clamp(0, 255);
        rgba[targetIndex + 1] = (color.g * 255).round().clamp(0, 255);
        rgba[targetIndex + 2] = (color.b * 255).round().clamp(0, 255);
        rgba[targetIndex + 3] = 255;
      }
    }

    final completer = Completer<ui.Image>();
    ui.decodeImageFromPixels(
      rgba,
      width,
      height,
      ui.PixelFormat.rgba8888,
      completer.complete,
    );
    final image = await completer.future;
    if (mounted) {
      setState(() => _raster = image);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.mapData.available) {
      return const Center(child: Text('Select a map to view occupancy data.'));
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final aspectRatio = widget.mapData.width / widget.mapData.height;
        return Center(
          child: AspectRatio(
            aspectRatio: aspectRatio,
            child: LayoutBuilder(
              builder: (context, paintConstraints) {
                return GestureDetector(
                  onTapUp: widget.onSectionTap == null
                      ? null
                      : (details) {
                          widget.onSectionTap!(
                            _sectionAt(details.localPosition, paintConstraints),
                          );
                        },
                  onPanStart: widget.selectionEnabled
                      ? (details) {
                          widget.onSelectionChanged(
                            _selectionFrom(
                              details.localPosition,
                              details.localPosition,
                              paintConstraints,
                            ),
                          );
                        }
                      : null,
                  onPanUpdate: widget.selectionEnabled
                      ? (details) {
                          final current =
                              widget.selection ??
                              const RectSelection(
                                left: 0,
                                top: 0,
                                right: 0,
                                bottom: 0,
                              );
                          widget.onSelectionChanged(
                            _selectionFrom(
                              Offset(
                                current.left * paintConstraints.maxWidth,
                                current.top * paintConstraints.maxHeight,
                              ),
                              details.localPosition,
                              paintConstraints,
                            ),
                          );
                        }
                      : null,
                  child: CustomPaint(
                    painter: _MapPainter(
                      raster: _raster,
                      selection: widget.selection,
                      mapData: widget.mapData,
                      robotPose: widget.robotPose,
                      sections: widget.sections,
                      selectedSectionIds: widget.selectedSectionIds,
                    ),
                    child: const SizedBox.expand(),
                  ),
                );
              },
            ),
          ),
        );
      },
    );
  }

  MapSection? _sectionAt(Offset point, BoxConstraints constraints) {
    for (final section in widget.sections.reversed) {
      final polygon = _sectionPolygon(section, constraints.biggest);
      if (_containsPoint(polygon, point)) {
        return section;
      }
    }
    return null;
  }

  List<Offset> _sectionPolygon(MapSection section, Size size) {
    return [
      for (final point in section.polygon)
        if (point.length >= 2) _worldToCanvas(point[0], point[1], size),
    ];
  }

  Offset _worldToCanvas(double worldX, double worldY, Size size) {
    final mapX = (worldX - widget.mapData.originX) / widget.mapData.resolution;
    final mapY = (worldY - widget.mapData.originY) / widget.mapData.resolution;
    return Offset(
      (mapX / widget.mapData.width) * size.width,
      (1 - (mapY / widget.mapData.height)) * size.height,
    );
  }

  bool _containsPoint(List<Offset> polygon, Offset point) {
    if (polygon.length < 3) {
      return false;
    }

    var inside = false;
    var previous = polygon.length - 1;
    for (var current = 0; current < polygon.length; current++) {
      final currentPoint = polygon[current];
      final previousPoint = polygon[previous];
      final intersects =
          (currentPoint.dy > point.dy) != (previousPoint.dy > point.dy) &&
          point.dx <
              (previousPoint.dx - currentPoint.dx) *
                      (point.dy - currentPoint.dy) /
                      (previousPoint.dy - currentPoint.dy) +
                  currentPoint.dx;
      if (intersects) {
        inside = !inside;
      }
      previous = current;
    }
    return inside;
  }

  RectSelection _selectionFrom(
    Offset start,
    Offset end,
    BoxConstraints constraints,
  ) {
    return RectSelection(
      left: (start.dx / constraints.maxWidth).clamp(0.0, 1.0),
      top: (start.dy / constraints.maxHeight).clamp(0.0, 1.0),
      right: (end.dx / constraints.maxWidth).clamp(0.0, 1.0),
      bottom: (end.dy / constraints.maxHeight).clamp(0.0, 1.0),
    );
  }
}

class _MapPainter extends CustomPainter {
  const _MapPainter({
    required this.raster,
    required this.selection,
    required this.mapData,
    required this.robotPose,
    required this.sections,
    required this.selectedSectionIds,
  });

  final ui.Image? raster;
  final RectSelection? selection;
  final SweePiMapData mapData;
  final RobotPose? robotPose;
  final List<MapSection> sections;
  final Set<String> selectedSectionIds;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xFFE4ECE7),
    );

    if (raster != null) {
      paintImage(
        canvas: canvas,
        rect: Offset.zero & size,
        image: raster!,
        fit: BoxFit.fill,
        filterQuality: FilterQuality.none,
      );
    }

    _drawGrid(canvas, size);
    _drawSections(canvas, size);

    if (robotPose != null && mapData.width > 0 && mapData.height > 0) {
      final mapX = (robotPose!.x - mapData.originX) / mapData.resolution;
      final mapY = (robotPose!.y - mapData.originY) / mapData.resolution;
      final dx = mapX / mapData.width * size.width;
      final dy = (1 - (mapY / mapData.height)) * size.height;
      canvas.drawCircle(
        Offset(dx, dy),
        6,
        Paint()..color = const Color(0xFF0D67B5),
      );
    }

    if (selection != null) {
      final rect = selection!.normalized();
      final selectionRect = Rect.fromLTRB(
        rect.left * size.width,
        rect.top * size.height,
        rect.right * size.width,
        rect.bottom * size.height,
      );
      canvas.drawRect(selectionRect, Paint()..color = const Color(0x55288A63));
      canvas.drawRect(
        selectionRect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = const Color(0xFF1E6B52),
      );
    }

    canvas.drawRect(
      Offset.zero & size,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = const Color(0xFF5A6D63),
    );
  }

  void _drawSections(Canvas canvas, Size size) {
    for (final section in sections) {
      final points = [
        for (final point in section.polygon)
          if (point.length >= 2) _worldToCanvas(point[0], point[1], size),
      ];
      if (points.length < 3) {
        continue;
      }

      final selected = selectedSectionIds.contains(section.sectionId);
      final path = Path()..moveTo(points.first.dx, points.first.dy);
      for (final point in points.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      path.close();

      canvas.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.fill
          ..color = selected
              ? const Color(0x6639A275)
              : const Color(0x33288A63),
      );
      canvas.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = selected ? 3 : 1.5
          ..color = selected
              ? const Color(0xFF0D67B5)
              : const Color(0xFF288A63),
      );
    }
  }

  Offset _worldToCanvas(double worldX, double worldY, Size size) {
    final mapX = (worldX - mapData.originX) / mapData.resolution;
    final mapY = (worldY - mapData.originY) / mapData.resolution;
    return Offset(
      (mapX / mapData.width) * size.width,
      (1 - (mapY / mapData.height)) * size.height,
    );
  }

  void _drawGrid(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.5
      ..color = const Color(0x223A4A42);
    const lines = 10;
    for (var i = 1; i < lines; i++) {
      final dx = size.width * i / lines;
      final dy = size.height * i / lines;
      canvas.drawLine(Offset(dx, 0), Offset(dx, size.height), paint);
      canvas.drawLine(Offset(0, dy), Offset(size.width, dy), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _MapPainter oldDelegate) {
    return oldDelegate.raster != raster ||
        oldDelegate.selection != selection ||
        oldDelegate.mapData.mapId != mapData.mapId ||
        oldDelegate.robotPose != robotPose ||
        oldDelegate.sections != sections ||
        oldDelegate.selectedSectionIds != selectedSectionIds;
  }
}
