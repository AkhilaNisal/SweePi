import 'package:flutter_test/flutter_test.dart';
import 'package:sweepi/core/models/cleaning_models.dart';
import 'package:sweepi/core/models/map_models.dart';
import 'package:sweepi/core/models/robot_models.dart';
import 'package:sweepi/core/network/robot_api_client.dart';

void main() {
  test('MapSection parses and serializes rectangular bounds', () {
    final section = MapSection.fromJson({
      'section_id': 'section_1',
      'name': 'Section 1',
      'bounds': {'x': 1.2, 'y': 0.8, 'width': 2.0, 'height': 1.5},
    });

    expect(section.sectionId, 'section_1');
    expect(section.bounds.x, 1.2);
    expect(section.toJson(), {
      'section_id': 'section_1',
      'name': 'Section 1',
      'bounds': {'x': 1.2, 'y': 0.8, 'width': 2.0, 'height': 1.5},
    });
  });

  test('map list parses top-level items with bounds sections', () {
    final items = (({
      'items': [
        {
          'map_id': 'my_room',
          'name': 'My Room',
          'created_at': '2026-06-24T10:00:00Z',
          'updated_at': '2026-06-24T10:30:00Z',
          'resolution': 0.05,
          'width': 384,
          'height': 384,
          'sections': [
            {
              'section_id': 'section_1',
              'bounds': {'x': 1, 'y': 2, 'width': 3, 'height': 4},
            },
          ],
        },
      ],
    })['items'] as List)
        .whereType<Map>()
        .map((item) => SweePiMapMetadata.fromJson(item.cast<String, dynamic>()))
        .toList();

    expect(items, hasLength(1));
    expect(items.first.sections.single.bounds.height, 4);
  });

  test('cleaning start body for full-map includes mandatory fields', () {
    final body = buildCleaningStartRequestBody(
      mapId: 'my_room',
      cleaningMode: 'full-map',
      sections: const [],
      initialPose: const RobotPose(x: 0, y: 0, yaw: 0, frame: 'map'),
    );

    expect(body['map_id'], 'my_room');
    expect(body['cleaning_mode'], 'full-map');
    expect(body['sections'], isEmpty);
    expect(body['initial_pose'], {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'frame': 'map'});
    expect(body.containsKey('auto_start'), isFalse);
  });

  test('cleaning start body for multi-section uses processed map shape', () {
    final mapData = SweePiMapData(
      mapId: 'my_room',
      name: 'My Room',
      resolution: 0.05,
      originX: -10,
      originY: -10,
      width: 2,
      height: 2,
      occupancy: const [0, 0, 100, -1],
    );
    const sections = [
      MapSection(
        sectionId: 'section_1',
        name: 'Section 1',
        bounds: SectionBounds(x: 1, y: 2, width: 3, height: 4),
      ),
      MapSection(
        sectionId: 'section_2',
        name: 'Section 2',
        bounds: SectionBounds(x: 5, y: 6, width: 7, height: 8),
      ),
    ];

    final body = buildCleaningStartRequestBody(
      mapId: 'my_room',
      cleaningMode: 'sections',
      sections: sections,
      processedMap: mapData,
      initialPose: const RobotPose(x: 0, y: 0, yaw: 0, frame: 'map'),
    );

    expect(body['cleaning_mode'], 'sections');
    expect(body['sections'], hasLength(2));
    expect((body['processed_map'] as Map).keys, {
      'width',
      'height',
      'resolution',
      'origin',
      'occupancy',
    });
  });

  test('standard API error fields parse from response wrapper', () {
    final fields = ApiResponseFields.fromJson({
      'success': false,
      'message': 'initial_pose is required.',
      'error': {
        'code': 'VALIDATION_ERROR',
        'details': {'field': 'initial_pose'},
      },
      'timestamp': '2026-06-24T12:00:00Z',
    });

    expect(fields.success, isFalse);
    expect(fields.message, 'initial_pose is required.');
    expect(fields.error?.code, 'VALIDATION_ERROR');
    expect(fields.error?.details['field'], 'initial_pose');
  });
}
