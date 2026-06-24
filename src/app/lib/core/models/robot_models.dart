import 'map_models.dart';

class RobotBattery {
  const RobotBattery({required this.percent, required this.charging});

  factory RobotBattery.fromJson(Map<String, dynamic> json) {
    return RobotBattery(
      percent: (json['percent'] as num?)?.toInt() ?? 0,
      charging: json['charging'] as bool? ?? false,
    );
  }

  static const empty = RobotBattery(percent: 0, charging: false);

  final int percent;
  final bool charging;
}

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

  Map<String, dynamic> toJson() {
    return {'x': x, 'y': y, 'yaw': yaw, 'frame': frame};
  }
}

class RobotMapState {
  const RobotMapState({required this.mapId, required this.name});

  factory RobotMapState.fromJson(Map<String, dynamic> json) {
    return RobotMapState(
      mapId: json['map_id'] as String?,
      name: json['name'] as String?,
    );
  }

  static const empty = RobotMapState(mapId: null, name: null);

  final String? mapId;
  final String? name;
}

class RobotCleaningState {
  const RobotCleaningState({
    required this.active,
    required this.taskId,
    required this.mapId,
    required this.cleaningMode,
    required this.sections,
    required this.progressPercent,
  });

  factory RobotCleaningState.fromJson(Map<String, dynamic> json) {
    return RobotCleaningState(
      active: json['active'] as bool? ?? false,
      taskId: json['task_id'] as String?,
      mapId: json['map_id'] as String?,
      cleaningMode: json['cleaning_mode'] as String?,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
    );
  }

  static const empty = RobotCleaningState(
    active: false,
    taskId: null,
    mapId: null,
    cleaningMode: null,
    sections: [],
    progressPercent: 0,
  );

  final bool active;
  final String? taskId;
  final String? mapId;
  final String? cleaningMode;
  final List<MapSection> sections;
  final double progressPercent;
}

class RobotExplorationState {
  const RobotExplorationState({
    required this.active,
    required this.mapName,
    required this.mode,
  });

  factory RobotExplorationState.fromJson(Map<String, dynamic> json) {
    return RobotExplorationState(
      active: json['active'] as bool? ?? false,
      mapName: json['map_name'] as String?,
      mode: json['mode'] as String?,
    );
  }

  static const empty = RobotExplorationState(
    active: false,
    mapName: null,
    mode: null,
  );

  final bool active;
  final String? mapName;
  final String? mode;
}

class RobotNavState {
  const RobotNavState({required this.executionStatus});

  factory RobotNavState.fromJson(Map<String, dynamic> json) {
    return RobotNavState(
      executionStatus: json['execution_status'] as String? ?? 'UNKNOWN',
    );
  }

  static const empty = RobotNavState(executionStatus: 'OFFLINE');

  final String executionStatus;
}

class RobotStatus {
  const RobotStatus({
    required this.robotId,
    required this.state,
    required this.mode,
    required this.battery,
    required this.pose,
    required this.map,
    required this.cleaning,
    required this.exploration,
    required this.nav,
    required this.errors,
    required this.warnings,
  });

  factory RobotStatus.fromJson(Map<String, dynamic> json) {
    return RobotStatus(
      robotId: json['robot_id'] as String? ?? 'unknown',
      state: json['state'] as String? ?? 'offline',
      mode: json['mode'] as String? ?? 'automatic',
      battery: json['battery'] is Map
          ? RobotBattery.fromJson(
              (json['battery'] as Map).cast<String, dynamic>(),
            )
          : RobotBattery.empty,
      pose: json['pose'] is Map
          ? RobotPose.fromJson((json['pose'] as Map).cast<String, dynamic>())
          : null,
      map: json['map'] is Map
          ? RobotMapState.fromJson((json['map'] as Map).cast<String, dynamic>())
          : RobotMapState.empty,
      cleaning: json['cleaning'] is Map
          ? RobotCleaningState.fromJson(
              (json['cleaning'] as Map).cast<String, dynamic>(),
            )
          : RobotCleaningState.empty,
      exploration: json['exploration'] is Map
          ? RobotExplorationState.fromJson(
              (json['exploration'] as Map).cast<String, dynamic>(),
            )
          : RobotExplorationState.empty,
      nav: json['nav'] is Map
          ? RobotNavState.fromJson((json['nav'] as Map).cast<String, dynamic>())
          : RobotNavState.empty,
      errors: List<String>.from(json['errors'] as List? ?? const []),
      warnings: List<String>.from(json['warnings'] as List? ?? const []),
    );
  }

  static const offline = RobotStatus(
    robotId: 'offline',
    state: 'offline',
    mode: 'automatic',
    battery: RobotBattery.empty,
    pose: null,
    map: RobotMapState.empty,
    cleaning: RobotCleaningState.empty,
    exploration: RobotExplorationState.empty,
    nav: RobotNavState.empty,
    errors: [],
    warnings: [],
  );

  final String robotId;
  final String state;
  final String mode;
  final RobotBattery battery;
  final RobotPose? pose;
  final RobotMapState map;
  final RobotCleaningState cleaning;
  final RobotExplorationState exploration;
  final RobotNavState nav;
  final List<String> errors;
  final List<String> warnings;
}
