import 'dart:math' as math;

import '../models/map_models.dart';

const occupiedCellValue = 100;

SweePiMapData buildProcessedSectionMap({
  required SweePiMapData mapData,
  required List<MapSection> sections,
  required int boundaryThicknessCells,
}) {
  if (!mapData.available) {
    throw ArgumentError('A valid map is required to build a section map.');
  }
  if (sections.isEmpty) {
    throw ArgumentError('At least one section is required.');
  }
  if (sections.any((section) => !section.bounds.isValid)) {
    throw ArgumentError('All sections must have valid rectangular bounds.');
  }

  final totalCells = mapData.width * mapData.height;
  final occupancy = List<int>.from(mapData.occupancy.take(totalCells));
  while (occupancy.length < totalCells) {
    occupancy.add(0);
  }

  final boundsList = sections
      .map((section) => _sectionCellBounds(mapData, section))
      .toList();
  final thickness = math.max(1, boundaryThicknessCells);

  for (var y = 0; y < mapData.height; y++) {
    for (var x = 0; x < mapData.width; x++) {
      final index = y * mapData.width + x;
      final insideAny = boundsList.any((bounds) => bounds.contains(x, y));
      final boundary = boundsList.any(
        (bounds) => bounds.contains(x, y) && bounds.isBoundary(x, y, thickness),
      );

      if (!insideAny || boundary) {
        occupancy[index] = occupiedCellValue;
      }
    }
  }

  return mapData.copyWith(occupancy: occupancy);
}

int defaultSectionBoundaryThicknessCells(SweePiMapData mapData) {
  if (mapData.resolution <= 0) {
    return 3;
  }
  return math.max(3, (0.15 / mapData.resolution).ceil());
}

_CellBounds _sectionCellBounds(SweePiMapData mapData, MapSection section) {
  final bounds = section.bounds;
  final start = _worldToCell(mapData, bounds.x, bounds.y);
  final end = _worldToCell(
    mapData,
    bounds.x + bounds.width,
    bounds.y + bounds.height,
  );

  return _CellBounds(
    left: math.min(start.x, end.x),
    right: math.max(start.x, end.x),
    bottom: math.min(start.y, end.y),
    top: math.max(start.y, end.y),
  );
}

_CellPoint _worldToCell(SweePiMapData mapData, double worldX, double worldY) {
  final x = ((worldX - mapData.originX) / mapData.resolution).floor();
  final y = ((worldY - mapData.originY) / mapData.resolution).floor();
  return _CellPoint(
    x: x.clamp(0, mapData.width - 1).toInt(),
    y: y.clamp(0, mapData.height - 1).toInt(),
  );
}

class _CellBounds {
  const _CellBounds({
    required this.left,
    required this.right,
    required this.bottom,
    required this.top,
  });

  final int left;
  final int right;
  final int bottom;
  final int top;

  bool contains(int x, int y) {
    return x >= left && x <= right && y >= bottom && y <= top;
  }

  bool isBoundary(int x, int y, int thickness) {
    return x - left < thickness ||
        right - x < thickness ||
        y - bottom < thickness ||
        top - y < thickness;
  }
}

class _CellPoint {
  const _CellPoint({required this.x, required this.y});

  final int x;
  final int y;
}
