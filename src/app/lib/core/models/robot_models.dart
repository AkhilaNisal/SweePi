class RobotPose {
  const RobotPose({
    required this.x,
    required this.y,
    required this.yaw,
    required this.frame,
  });

  factory RobotPose.fromJson(Map<String, dynamic> json) {
    return RobotPose(
      x: (json['x'] as num?)?.toDouble() ?? 0,
      y: (json['y'] as num?)?.toDouble() ?? 0,
      yaw: (json['yaw'] as num?)?.toDouble() ?? 0,
      frame: json['frame'] as String? ?? 'map',
    );
  }

  final double x;
  final double y;
  final double yaw;
  final String frame;
}

class RobotStatus {
  const RobotStatus({
    required this.state,
    required this.mode,
    required this.progressPercent,
    required this.executionStatus,
    required this.errors,
    required this.warnings,
    required this.pose,
    required this.selection,
    required this.taskId,
  });

  factory RobotStatus.fromJson(Map<String, dynamic> json) {
    final cleaning = (json['cleaning'] as Map?)?.cast<String, dynamic>() ?? {};
    final nav = (json['nav'] as Map?)?.cast<String, dynamic>() ?? {};
    return RobotStatus(
      state: json['state'] as String? ?? 'offline',
      mode: json['mode'] as String? ?? 'auto',
      progressPercent:
          (cleaning['progress_percent'] as num?)?.toDouble() ?? 0,
      executionStatus: nav['execution_status'] as String? ?? 'unknown',
      errors: List<String>.from(json['errors'] as List? ?? const []),
      warnings: List<String>.from(json['warnings'] as List? ?? const []),
      pose: json['pose'] is Map<String, dynamic>
          ? RobotPose.fromJson(json['pose'] as Map<String, dynamic>)
          : null,
      selection:
          (cleaning['selection'] as Map?)?.cast<String, dynamic>() ?? const {},
      taskId: cleaning['task_id'] as String?,
    );
  }

  static const offline = RobotStatus(
    state: 'offline',
    mode: 'auto',
    progressPercent: 0,
    executionStatus: 'offline',
    errors: [],
    warnings: [],
    pose: null,
    selection: {},
    taskId: null,
  );

  final String state;
  final String mode;
  final double progressPercent;
  final String executionStatus;
  final List<String> errors;
  final List<String> warnings;
  final RobotPose? pose;
  final Map<String, dynamic> selection;
  final String? taskId;
}

class MapPayload {
  const MapPayload({
    required this.available,
    required this.mapId,
    required this.revision,
    required this.resolution,
    required this.originX,
    required this.originY,
    required this.width,
    required this.height,
    required this.occupancy,
    required this.coverage,
    required this.metadata,
    required this.robotPose,
  });

  factory MapPayload.fromJson(Map<String, dynamic> json) {
    return MapPayload(
      available: json['available'] as bool? ?? false,
      mapId: json['map_id'] as String? ?? 'live_map',
      revision: (json['revision'] as num?)?.toInt() ?? 0,
      resolution: (json['resolution'] as num?)?.toDouble() ?? 0.05,
      originX: ((json['origin'] as Map?)?['x'] as num?)?.toDouble() ?? 0,
      originY: ((json['origin'] as Map?)?['y'] as num?)?.toDouble() ?? 0,
      width: (json['width'] as num?)?.toInt() ?? 0,
      height: (json['height'] as num?)?.toInt() ?? 0,
      occupancy: List<int>.from(json['occupancy'] as List? ?? const []),
      coverage: json['coverage'] == null
          ? null
          : List<int>.from(json['coverage'] as List),
      metadata:
          (json['metadata'] as Map?)?.cast<String, dynamic>() ?? const {},
      robotPose: json['robot_pose'] is Map<String, dynamic>
          ? RobotPose.fromJson(json['robot_pose'] as Map<String, dynamic>)
          : null,
    );
  }

  static const empty = MapPayload(
    available: false,
    mapId: 'live_map',
    revision: 0,
    resolution: 0.05,
    originX: 0,
    originY: 0,
    width: 0,
    height: 0,
    occupancy: [],
    coverage: null,
    metadata: {},
    robotPose: null,
  );

  final bool available;
  final String mapId;
  final int revision;
  final double resolution;
  final double originX;
  final double originY;
  final int width;
  final int height;
  final List<int> occupancy;
  final List<int>? coverage;
  final Map<String, dynamic> metadata;
  final RobotPose? robotPose;
}

class ScheduleItem {
  const ScheduleItem({
    required this.id,
    required this.enabled,
    required this.timeLocal,
    required this.days,
    required this.selection,
  });

  factory ScheduleItem.fromJson(Map<String, dynamic> json) {
    return ScheduleItem(
      id: json['id'] as String? ?? '',
      enabled: json['enabled'] as bool? ?? true,
      timeLocal: json['time_local'] as String? ?? '09:00',
      days: List<String>.from(json['days'] as List? ?? const []),
      selection:
          (json['selection'] as Map?)?.cast<String, dynamic>() ?? const {},
    );
  }

  final String id;
  final bool enabled;
  final String timeLocal;
  final List<String> days;
  final Map<String, dynamic> selection;
}

class HistoryItem {
  const HistoryItem({
    required this.taskId,
    required this.taskType,
    required this.startedAt,
    required this.endedAt,
    required this.result,
    required this.coveragePercent,
  });

  factory HistoryItem.fromJson(Map<String, dynamic> json) {
    return HistoryItem(
      taskId: json['task_id'] as String? ?? '',
      taskType: json['task_type'] as String? ?? 'full',
      startedAt: json['started_at'] as String? ?? '',
      endedAt: json['ended_at'] as String?,
      result: json['result'] as String?,
      coveragePercent: (json['coverage_percent'] as num?)?.toDouble(),
    );
  }

  final String taskId;
  final String taskType;
  final String startedAt;
  final String? endedAt;
  final String? result;
  final double? coveragePercent;
}
