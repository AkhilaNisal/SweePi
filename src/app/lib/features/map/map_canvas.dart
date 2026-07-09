import 'dart:async';
import 'dart:math' as math;
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
    this.plannedInitialPose,
    this.onInitialPoseChanged,
    this.initialPoseEnabled = false,
  });

  final SweePiMapData mapData;
  final RectSelection? selection;
  final ValueChanged<RectSelection?> onSelectionChanged;
  final RobotPose? robotPose;
  final List<MapSection> sections;
  final Set<String> selectedSectionIds;
  final ValueChanged<MapSection?>? onSectionTap;
  final bool selectionEnabled;
  final RobotPose? plannedInitialPose;
  final ValueChanged<RobotPose?>? onInitialPoseChanged;
  final bool initialPoseEnabled;

  @override
  State<MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<MapCanvas> {
  static const double _initialPoseGrabHitRadius = 68;

  ui.Image? _raster;
  Offset? _poseDragStart;
  bool _movingInitialPose = false;

  @override
  void initState() {
    super.initState();
    _rebuildRaster();
  }

  @override
  void didUpdateWidget(covariant MapCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.mapData.mapId != widget.mapData.mapId ||
        oldWidget.mapData.occupancy.length != widget.mapData.occupancy.length ||
        oldWidget.mapData.occupancy != widget.mapData.occupancy) {
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
                  behavior: HitTestBehavior.opaque,
                  onTapUp: widget.onSectionTap == null
                      ? null
                      : (details) {
                          if (widget.initialPoseEnabled &&
                              _isInsideInitialPoseHitArea(
                                details.localPosition,
                                paintConstraints.biggest,
                              )) {
                            return;
                          }
                          widget.onSectionTap!(
                            _sectionAt(details.localPosition, paintConstraints),
                          );
                        },
                  onPanStart:
                      (widget.selectionEnabled || widget.initialPoseEnabled)
                      ? (details) => _handlePanStart(details, paintConstraints)
                      : null,
                  onPanUpdate:
                      (widget.selectionEnabled || widget.initialPoseEnabled)
                      ? (details) => _handlePanUpdate(details, paintConstraints)
                      : null,
                  onPanEnd: widget.initialPoseEnabled
                      ? (_) => _clearInitialPoseGesture()
                      : null,
                  onLongPressStart: widget.initialPoseEnabled
                      ? (details) => _handleInitialPoseLongPressStart(
                          details,
                          paintConstraints,
                        )
                      : null,
                  onLongPressMoveUpdate: widget.initialPoseEnabled
                      ? (details) => _handleInitialPoseLongPressMove(
                          details,
                          paintConstraints,
                        )
                      : null,
                  onLongPressEnd: widget.initialPoseEnabled
                      ? (_) => _clearInitialPoseGesture()
                      : null,
                  child: CustomPaint(
                    painter: _MapPainter(
                      raster: _raster,
                      selection: widget.selection,
                      mapData: widget.mapData,
                      robotPose: widget.robotPose,
                      plannedInitialPose: widget.plannedInitialPose,
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

  void _handlePanStart(DragStartDetails details, BoxConstraints constraints) {
    if (widget.initialPoseEnabled) {
      final initialPoseCenter = _initialPoseCanvasCenter(constraints.biggest);
      final dragStart =
          initialPoseCenter != null &&
              (details.localPosition - initialPoseCenter).distance <=
                  _initialPoseGrabHitRadius
          ? initialPoseCenter
          : details.localPosition;
      _poseDragStart = dragStart;
      widget.onInitialPoseChanged?.call(
        _poseFromDrag(dragStart, details.localPosition, constraints),
      );
      return;
    }

    widget.onSelectionChanged(
      _selectionFrom(details.localPosition, details.localPosition, constraints),
    );
  }

  void _handlePanUpdate(DragUpdateDetails details, BoxConstraints constraints) {
    if (widget.initialPoseEnabled) {
      if (_movingInitialPose) {
        return;
      }
      widget.onInitialPoseChanged?.call(
        _poseFromDrag(
          _poseDragStart ?? details.localPosition,
          details.localPosition,
          constraints,
        ),
      );
      return;
    }

    final current =
        widget.selection ??
        const RectSelection(left: 0, top: 0, right: 0, bottom: 0);
    widget.onSelectionChanged(
      _selectionFrom(
        Offset(
          current.left * constraints.maxWidth,
          current.top * constraints.maxHeight,
        ),
        details.localPosition,
        constraints,
      ),
    );
  }

  void _handleInitialPoseLongPressStart(
    LongPressStartDetails details,
    BoxConstraints constraints,
  ) {
    final initialPoseCenter = _initialPoseCanvasCenter(constraints.biggest);
    if (initialPoseCenter == null ||
        (details.localPosition - initialPoseCenter).distance >
            _initialPoseGrabHitRadius) {
      return;
    }

    _movingInitialPose = true;
  }

  void _handleInitialPoseLongPressMove(
    LongPressMoveUpdateDetails details,
    BoxConstraints constraints,
  ) {
    if (!_movingInitialPose) {
      return;
    }

    widget.onInitialPoseChanged?.call(
      _poseAtPoint(details.localPosition, constraints),
    );
  }

  void _clearInitialPoseGesture() {
    _poseDragStart = null;
    _movingInitialPose = false;
  }

  MapSection? _sectionAt(Offset point, BoxConstraints constraints) {
    for (final section in widget.sections.reversed) {
      final rect = _sectionRect(section, constraints.biggest);
      if (rect.contains(point)) {
        return section;
      }
    }
    return null;
  }

  Rect _sectionRect(MapSection section, Size size) {
    final bounds = section.bounds;
    final first = _worldToCanvas(bounds.x, bounds.y, size);
    final second = _worldToCanvas(
      bounds.x + bounds.width,
      bounds.y + bounds.height,
      size,
    );
    return Rect.fromPoints(first, second);
  }

  Offset _worldToCanvas(double worldX, double worldY, Size size) {
    final mapX = (worldX - widget.mapData.originX) / widget.mapData.resolution;
    final mapY = (worldY - widget.mapData.originY) / widget.mapData.resolution;
    return Offset(
      (mapX / widget.mapData.width) * size.width,
      (1 - (mapY / widget.mapData.height)) * size.height,
    );
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

  RobotPose _poseFromDrag(
    Offset start,
    Offset end,
    BoxConstraints constraints,
  ) {
    final worldStart = _canvasToWorld(start, constraints.biggest);
    final worldEnd = _canvasToWorld(end, constraints.biggest);
    final dx = worldEnd.dx - worldStart.dx;
    final dy = worldEnd.dy - worldStart.dy;
    final yaw = dx.abs() + dy.abs() < 0.0001
        ? widget.plannedInitialPose?.yaw ?? 0.0
        : math.atan2(dy, dx);
    return RobotPose(
      x: worldStart.dx,
      y: worldStart.dy,
      yaw: yaw,
      frame: 'map',
    );
  }

  RobotPose _poseAtPoint(Offset point, BoxConstraints constraints) {
    final world = _canvasToWorld(point, constraints.biggest);
    return RobotPose(
      x: world.dx,
      y: world.dy,
      yaw: widget.plannedInitialPose?.yaw ?? 0.0,
      frame: 'map',
    );
  }

  Offset _canvasToWorld(Offset point, Size size) {
    final mapX = (point.dx / size.width) * widget.mapData.width;
    final mapY = (1 - (point.dy / size.height)) * widget.mapData.height;
    return Offset(
      widget.mapData.originX + mapX * widget.mapData.resolution,
      widget.mapData.originY + mapY * widget.mapData.resolution,
    );
  }

  Offset? _initialPoseCanvasCenter(Size size) {
    final pose = widget.plannedInitialPose;
    if (pose == null) {
      return null;
    }
    return _worldToCanvas(pose.x, pose.y, size);
  }

  bool _isInsideInitialPoseHitArea(Offset point, Size size) {
    final initialPoseCenter = _initialPoseCanvasCenter(size);
    return initialPoseCenter != null &&
        (point - initialPoseCenter).distance <= _initialPoseGrabHitRadius;
  }
}

class _MapPainter extends CustomPainter {
  const _MapPainter({
    required this.raster,
    required this.selection,
    required this.mapData,
    required this.robotPose,
    required this.plannedInitialPose,
    required this.sections,
    required this.selectedSectionIds,
  });

  final ui.Image? raster;
  final RectSelection? selection;
  final SweePiMapData mapData;
  final RobotPose? robotPose;
  final RobotPose? plannedInitialPose;
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
      _drawPoseMarker(canvas, size, robotPose!, const Color(0xFF0D67B5), 6);
    }

    if (plannedInitialPose != null && mapData.width > 0 && mapData.height > 0) {
      _drawPoseMarker(
        canvas,
        size,
        plannedInitialPose!,
        const Color(0xFFE56B2F),
        7,
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
      final rect = _sectionRect(section, size);
      if (rect.isEmpty) {
        continue;
      }

      final selected = selectedSectionIds.contains(section.sectionId);

      if (!selected) {
        canvas.drawRect(
          rect,
          Paint()
            ..style = PaintingStyle.fill
            ..color = const Color(0x33288A63),
        );
      }
      canvas.drawRect(
        rect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = selected ? 3 : 1.5
          ..color = selected ? Colors.black : const Color(0xFF288A63),
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

  Rect _sectionRect(MapSection section, Size size) {
    final bounds = section.bounds;
    final first = _worldToCanvas(bounds.x, bounds.y, size);
    final second = _worldToCanvas(
      bounds.x + bounds.width,
      bounds.y + bounds.height,
      size,
    );
    return Rect.fromPoints(first, second);
  }

  void _drawPoseMarker(
    Canvas canvas,
    Size size,
    RobotPose pose,
    Color color,
    double radius,
  ) {
    final center = _worldToCanvas(pose.x, pose.y, size);
    final heading = Offset(math.cos(pose.yaw) * 18, -math.sin(pose.yaw) * 18);
    final paint = Paint()
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawCircle(center, radius, Paint()..color = color);
    canvas.drawLine(center, center + heading, paint);
    canvas.drawCircle(
      center,
      radius + 3,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = Colors.white,
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
        oldDelegate.plannedInitialPose != plannedInitialPose ||
        oldDelegate.sections != sections ||
        oldDelegate.selectedSectionIds != selectedSectionIds;
  }
}
