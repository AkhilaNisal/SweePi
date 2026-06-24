import 'package:flutter_test/flutter_test.dart';
import 'package:sweepi/core/map/processed_section_map.dart';
import 'package:sweepi/core/models/map_models.dart';

void main() {
  test('buildProcessedSectionMap blocks outside rectangular section', () {
    final occupancy = List<int>.filled(8 * 8, 0);
    occupancy[3 * 8 + 3] = occupiedCellValue;

    final mapData = SweePiMapData(
      mapId: 'room_map',
      name: 'Room',
      resolution: 1,
      originX: 10,
      originY: 20,
      originYaw: 0.25,
      width: 8,
      height: 8,
      occupancy: occupancy,
    );
    const section = MapSection(
      sectionId: 'sec_1',
      name: 'Center',
      bounds: SectionBounds(x: 12, y: 22, width: 3, height: 3),
    );

    final processed = buildProcessedSectionMap(
      mapData: mapData,
      sections: [section],
      boundaryThicknessCells: 1,
    );

    expect(processed.mapId, mapData.mapId);
    expect(processed.width, mapData.width);
    expect(processed.height, mapData.height);
    expect(processed.resolution, mapData.resolution);
    expect(processed.originX, mapData.originX);
    expect(processed.originY, mapData.originY);
    expect(processed.originYaw, mapData.originYaw);

    expect(_cell(processed, 1, 3), occupiedCellValue);
    expect(_cell(processed, 6, 3), occupiedCellValue);
    expect(_cell(processed, 3, 1), occupiedCellValue);
    expect(_cell(processed, 3, 6), occupiedCellValue);

    for (var x = 2; x <= 5; x++) {
      expect(_cell(processed, x, 2), occupiedCellValue);
      expect(_cell(processed, x, 5), occupiedCellValue);
    }
    for (var y = 2; y <= 5; y++) {
      expect(_cell(processed, 2, y), occupiedCellValue);
      expect(_cell(processed, 5, y), occupiedCellValue);
    }

    expect(_cell(processed, 3, 3), occupiedCellValue);
    expect(_cell(processed, 4, 4), 0);
  });

  test('buildProcessedSectionMap preserves multiple rectangular sections', () {
    final mapData = SweePiMapData(
      mapId: 'room_map',
      name: 'Room',
      resolution: 1,
      originX: 0,
      originY: 0,
      width: 10,
      height: 10,
      occupancy: List<int>.filled(10 * 10, 0),
    );
    const first = MapSection(
      sectionId: 'sec_1',
      name: 'First',
      bounds: SectionBounds(x: 1, y: 1, width: 3, height: 3),
    );
    const second = MapSection(
      sectionId: 'sec_2',
      name: 'Second',
      bounds: SectionBounds(x: 6, y: 6, width: 3, height: 3),
    );

    final processed = buildProcessedSectionMap(
      mapData: mapData,
      sections: [first, second],
      boundaryThicknessCells: 1,
    );

    expect(_cell(processed, 2, 2), 0);
    expect(_cell(processed, 7, 7), 0);
    expect(_cell(processed, 5, 5), occupiedCellValue);
    expect(_cell(processed, 0, 0), occupiedCellValue);
  });

  test('buildProcessedSectionMap applies boundary thickness', () {
    final mapData = SweePiMapData(
      mapId: 'room_map',
      name: 'Room',
      resolution: 1,
      originX: 0,
      originY: 0,
      width: 8,
      height: 8,
      occupancy: List<int>.filled(8 * 8, 0),
    );
    const section = MapSection(
      sectionId: 'sec_1',
      name: 'Center',
      bounds: SectionBounds(x: 1, y: 1, width: 5, height: 5),
    );

    final processed = buildProcessedSectionMap(
      mapData: mapData,
      sections: [section],
      boundaryThicknessCells: 2,
    );

    expect(_cell(processed, 2, 3), occupiedCellValue);
    expect(_cell(processed, 3, 2), occupiedCellValue);
    expect(_cell(processed, 4, 4), 0);
  });
}

int _cell(SweePiMapData map, int x, int y) {
  return map.occupancy[y * map.width + x];
}
