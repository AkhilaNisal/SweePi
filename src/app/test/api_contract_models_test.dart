import 'dart:math' as math;

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
    final items =
        (({
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
                })['items']
                as List)
            .whereType<Map>()
            .map(
              (item) =>
                  SweePiMapMetadata.fromJson(item.cast<String, dynamic>()),
            )
            .toList();

    expect(items, hasLength(1));
    expect(items.first.sections.single.bounds.height, 4);
  });

  test('cleaning start body for full-map includes mandatory fields', () {
    final body = buildCleaningStartRequestBody(
      mapId: 'my_room',
      cleaningMode: 'full-map',
      sections: const [],
    );

    expect(body['map_id'], 'my_room');
    expect(body['cleaning_mode'], 'full-map');
    expect(body['sections'], isEmpty);
    expect(body.containsKey('initial_pose'), isFalse);
    expect(body.containsKey('auto_start'), isFalse);
  });

  test('initial pose body sends yaw in radians', () {
    const pose = RobotPose(x: 1.5, y: 2.5, yaw: math.pi / 2, frame: 'map');

    final body = buildInitialPoseRequestBody(
      mapId: 'my_room',
      initialPose: pose,
    );

    expect(body, {
      'map_id': 'my_room',
      'x': 1.5,
      'y': 2.5,
      'yaw': math.pi / 2,
      'frame': 'map',
    });
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
      'message': 'initial_pose must be sent separately after cleaning/start.',
      'error': {
        'code': 'VALIDATION_ERROR',
        'details': {
          'field': 'initial_pose',
          'use_endpoint': '/api/localization/initial-pose',
        },
      },
      'timestamp': '2026-06-24T12:00:00Z',
    });

    expect(fields.success, isFalse);
    expect(
      fields.message,
      'initial_pose must be sent separately after cleaning/start.',
    );
    expect(fields.error?.code, 'VALIDATION_ERROR');
    expect(fields.error?.details['field'], 'initial_pose');
    expect(
      fields.error?.details['use_endpoint'],
      '/api/localization/initial-pose',
    );
  });

  test('cleaning start response parses lifecycle fields', () {
    final response = CleaningStartResponse.fromJson({
      'success': true,
      'accepted': true,
      'completed': true,
      'task_finished': false,
      'command': 'prepare_cleaning',
      'message': 'Coverage prepared. Waiting for initial pose.',
      'error': null,
      'timestamp': '2026-06-24T12:00:00Z',
      'task_id': 'cleaning_20260624_001',
      'state': 'waiting_for_initial_pose',
      'map_id': 'my_room',
      'cleaning_mode': 'sections',
      'sections': [
        {'section_id': 'section_1', 'name': 'Section 1'},
      ],
      'initial_pose': null,
      'initial_pose_required': true,
      'progress_percent': 0.0,
      'next_steps': [
        'Set initial pose from RViz or POST /api/localization/initial-pose.',
        'Call POST /api/cleaning/validate.',
      ],
    });

    expect(response.commandSucceeded, isTrue);
    expect(response.completed, isTrue);
    expect(response.lifecycle.command, 'prepare_cleaning');
    expect(response.state, 'waiting_for_initial_pose');
    expect(response.initialPoseRequired, isTrue);
    expect(response.nextSteps, hasLength(2));
  });

  test('simple cleaning command response requires completed step', () {
    final response = SimpleCommandResponse.fromJson({
      'success': true,
      'accepted': true,
      'completed': false,
      'task_finished': false,
      'command': 'set_initial_pose',
      'message': 'Initial pose not confirmed yet.',
      'error': null,
      'timestamp': '2026-06-24T12:00:00Z',
      'state': 'initial_pose_failed',
      'initial_pose_received': true,
      'initial_pose_confirmed': false,
    });

    expect(response.accepted, isTrue);
    expect(response.completed, isFalse);
    expect(response.commandSucceeded, isFalse);
    expect(response.command, 'set_initial_pose');
    expect(response.initialPoseReceived, isTrue);
    expect(response.initialPoseConfirmed, isFalse);
  });

  test('cleaning validation and motion responses parse final API fields', () {
    final validation = SimpleCommandResponse.fromJson({
      'success': true,
      'message': 'Coverage validation completed successfully.',
      'error': null,
      'timestamp': '2026-06-24T12:00:00Z',
      'command': 'validate_cleaning',
      'accepted': true,
      'completed': true,
      'task_finished': false,
      'state': 'coverage_validated',
      'task_id': 'cleaning_20260624_001',
      'map_id': 'my_room',
      'coverage_map_id': 'my_room',
    });
    final motion = SimpleCommandResponse.fromJson({
      'success': true,
      'message': 'Cleaning motion started.',
      'error': null,
      'timestamp': '2026-06-24T12:00:00Z',
      'command': 'start_cleaning_motion',
      'accepted': true,
      'completed': true,
      'task_finished': false,
      'state': 'cleaning',
      'task_id': 'cleaning_20260624_001',
      'map_id': 'my_room',
      'coverage_map_id': 'my_room',
    });

    expect(validation.commandSucceeded, isTrue);
    expect(validation.command, 'validate_cleaning');
    expect(validation.coverageMapId, 'my_room');
    expect(motion.commandSucceeded, isTrue);
    expect(motion.command, 'start_cleaning_motion');
    expect(motion.state, 'cleaning');
  });

  test('cleaning status parses readiness and task lifecycle fields', () {
    final status = CleaningStatus.fromJson({
      'success': true,
      'message': 'Cleaning status fetched.',
      'error': null,
      'timestamp': '2026-06-24T12:00:00Z',
      'active': true,
      'state': 'cleaning',
      'task_id': 'cleaning_20260624_001',
      'map_id': 'my_room',
      'coverage_map_id': 'my_room',
      'cleaning_mode': 'sections',
      'sections': [
        {'section_id': 'section_1', 'name': 'Section 1'},
      ],
      'progress_percent': 42.5,
      'pose': {'x': 1.3, 'y': 0.9, 'yaw': 1.57, 'frame': 'map'},
      'paused': false,
      'initial_pose_received': true,
      'initial_pose_confirmed': true,
      'initial_pose_source': 'api',
      'pose_available': true,
      'coverage_path_available': true,
      'path_available': true,
      'coverage_map_available': true,
      'coverage_validated': true,
      'ready_to_validate': true,
      'ready_to_start_motion': false,
      'task_finished': false,
      'task_result': null,
      'last_error': null,
      'next_steps': ['Poll GET /api/cleaning/status.'],
      'nav': {'execution_status': 'RUNNING'},
    });

    expect(status.active, isTrue);
    expect(status.coverageMapId, 'my_room');
    expect(status.progressPercent, 42.5);
    expect(status.pose?.yaw, 1.57);
    expect(status.initialPoseConfirmed, isTrue);
    expect(status.coverageValidated, isTrue);
    expect(status.readyToValidate, isTrue);
    expect(status.readyToStartMotion, isFalse);
    expect(status.navExecutionStatus, 'RUNNING');
    expect(status.nextSteps, hasLength(1));
  });
}
