import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../core/models/robot_models.dart';
import '../app/app_controller.dart';

class MapCanvas extends StatefulWidget {
  const MapCanvas({
    super.key,
    required this.mapPayload,
    required this.selection,
    required this.onSelectionChanged,
  });

  final MapPayload mapPayload;
  final RectSelection? selection;
  final ValueChanged<RectSelection?> onSelectionChanged;

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
    if (oldWidget.mapPayload.revision != widget.mapPayload.revision) {
      _rebuildRaster();
    }
  }

  Future<void> _rebuildRaster() async {
    if (!widget.mapPayload.available ||
        widget.mapPayload.width == 0 ||
        widget.mapPayload.height == 0) {
      setState(() => _raster = null);
      return;
    }

    final width = widget.mapPayload.width;
    final height = widget.mapPayload.height;
    final rgba = Uint8List(width * height * 4);

    for (var mapY = 0; mapY < height; mapY++) {
      for (var mapX = 0; mapX < width; mapX++) {
        final sourceIndex = mapY * width + mapX;
        final targetY = height - 1 - mapY;
        final targetIndex = (targetY * width + mapX) * 4;
        final occupancy = widget.mapPayload.occupancy[sourceIndex];
        final coverage = widget.mapPayload.coverage?[sourceIndex];

        final color = switch (occupancy) {
          < 0 => const Color(0xFFC9D1D0),
          0 => coverage == 100
              ? const Color(0xFF8ED1A8)
              : const Color(0xFFF8FCF6),
          _ => const Color(0xFF25302B),
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
    if (!widget.mapPayload.available) {
      return const Center(child: Text('No live map is available yet.'));
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final aspectRatio = widget.mapPayload.width / widget.mapPayload.height;
        return Center(
          child: AspectRatio(
            aspectRatio: aspectRatio,
            child: GestureDetector(
              onPanStart: (details) =>
                  widget.onSelectionChanged(_selectionFrom(details.localPosition, details.localPosition, constraints)),
              onPanUpdate: (details) {
                final current = widget.selection ?? const RectSelection(left: 0, top: 0, right: 0, bottom: 0);
                widget.onSelectionChanged(
                  _selectionFrom(
                    Offset(current.left * constraints.maxWidth, current.top * constraints.maxHeight),
                    details.localPosition,
                    constraints,
                  ),
                );
              },
              child: CustomPaint(
                painter: _MapPainter(
                  raster: _raster,
                  selection: widget.selection,
                  mapPayload: widget.mapPayload,
                ),
                child: const SizedBox.expand(),
              ),
            ),
          ),
        );
      },
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
}

class _MapPainter extends CustomPainter {
  const _MapPainter({
    required this.raster,
    required this.selection,
    required this.mapPayload,
  });

  final ui.Image? raster;
  final RectSelection? selection;
  final MapPayload mapPayload;

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

    final robotPose = mapPayload.robotPose;
    if (robotPose != null && mapPayload.width > 0 && mapPayload.height > 0) {
      final mapX = (robotPose.x - mapPayload.originX) / mapPayload.resolution;
      final mapY = (robotPose.y - mapPayload.originY) / mapPayload.resolution;
      final dx = mapX / mapPayload.width * size.width;
      final dy = (1 - (mapY / mapPayload.height)) * size.height;
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
      canvas.drawRect(
        selectionRect,
        Paint()..color = const Color(0x55288A63),
      );
      canvas.drawRect(
        selectionRect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = const Color(0xFF1E6B52),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _MapPainter oldDelegate) {
    return oldDelegate.raster != raster ||
        oldDelegate.selection != selection ||
        oldDelegate.mapPayload.revision != mapPayload.revision;
  }
}
