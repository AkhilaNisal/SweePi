import 'dart:math' as math;

import '../models/map_models.dart';

const occupiedCellValue = 100;

SweePiMapData buildProcessedSectionMap({
  required SweePiMapData mapData,
  required MapSection section,
  required int boundaryThicknessCells,
}) {
  if (!mapData.available) {
    throw ArgumentError('A valid map is required to build a section map.');
  }
  if (section.polygon.length < 3) {
    throw ArgumentError('A section polygon must contain at least 3 points.');
  }

  final totalCells = mapData.width * mapData.height;
  final occupancy = List<int>.from(mapData.occupancy.take(totalCells));
  while (occupancy.length < totalCells) {
    occupancy.add(0);
  }

  final bounds = _sectionCellBounds(mapData, section);
  final thickness = math.max(1, boundaryThicknessCells);

  for (var y = 0; y < mapData.height; y++) {
    for (var x = 0; x < mapData.width; x++) {
      final index = y * mapData.width + x;
      final outside =
          x < bounds.left ||
          x > bounds.right ||
          y < bounds.bottom ||
          y > bounds.top;
      final boundary =
          x - bounds.left < thickness ||
          bounds.right - x < thickness ||
          y - bounds.bottom < thickness ||
          bounds.top - y < thickness;

      if (outside || boundary) {
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
  final xs = <int>[];
  final ys = <int>[];

  for (final point in section.polygon) {
    if (point.length < 2) {
      continue;
    }
    final cell = _worldToCell(mapData, point[0], point[1]);
    xs.add(cell.x);
    ys.add(cell.y);
  }

  if (xs.isEmpty || ys.isEmpty) {
    throw ArgumentError('A section polygon must contain valid [x, y] points.');
  }

  return _CellBounds(
    left: xs.reduce(math.min),
    right: xs.reduce(math.max),
    bottom: ys.reduce(math.min),
    top: ys.reduce(math.max),
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
}

class _CellPoint {
  const _CellPoint({required this.x, required this.y});

  final int x;
  final int y;
}
