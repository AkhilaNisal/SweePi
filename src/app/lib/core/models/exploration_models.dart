import 'cleaning_models.dart';
import 'robot_models.dart';

class ExplorationStatus {
  const ExplorationStatus({
    required this.common,
    required this.active,
    required this.state,
    required this.mode,
    required this.mapName,
    required this.mapAvailable,
    required this.progressPercent,
    required this.pose,
  });

  factory ExplorationStatus.fromJson(Map<String, dynamic> json) {
    return ExplorationStatus(
      common: ApiResponseFields.fromJson(json),
      active: json['active'] as bool? ?? false,
      state: json['state'] as String? ?? 'unknown',
      mode: json['mode'] as String? ?? 'automatic',
      mapName: json['map_name'] as String?,
      mapAvailable: json['map_available'] as bool? ?? false,
      progressPercent: (json['progress_percent'] as num?)?.toDouble(),
      pose: json['pose'] is Map
          ? RobotPose.fromJson((json['pose'] as Map).cast<String, dynamic>())
          : null,
    );
  }

  static const empty = ExplorationStatus(
    common: ApiResponseFields(
      success: true,
      message: 'Exploration status has not been loaded.',
      error: null,
      timestamp: null,
    ),
    active: false,
    state: 'idle',
    mode: 'automatic',
    mapName: null,
    mapAvailable: false,
    progressPercent: null,
    pose: null,
  );

  final ApiResponseFields common;
  final bool active;
  final String state;
  final String mode;
  final String? mapName;
  final bool mapAvailable;
  final double? progressPercent;
  final RobotPose? pose;

  String get message => common.message;
}

class ExplorationStartResponse {
  const ExplorationStartResponse({
    required this.common,
    required this.accepted,
    required this.state,
    required this.mode,
    required this.mapName,
  });

  factory ExplorationStartResponse.fromJson(Map<String, dynamic> json) {
    return ExplorationStartResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String? ?? '',
      mode: json['mode'] as String? ?? 'automatic',
      mapName: json['map_name'] as String? ?? '',
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String state;
  final String mode;
  final String mapName;

  String get message => common.message;
}

class ExplorationSwitchResponse {
  const ExplorationSwitchResponse({
    required this.common,
    required this.accepted,
    required this.state,
    required this.mode,
  });

  factory ExplorationSwitchResponse.fromJson(Map<String, dynamic> json) {
    return ExplorationSwitchResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String? ?? '',
      mode: json['mode'] as String? ?? 'automatic',
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String state;
  final String mode;

  String get message => common.message;
}

class ExplorationStopResponse {
  const ExplorationStopResponse({
    required this.common,
    required this.accepted,
    required this.state,
    required this.mapSaved,
    required this.mapId,
    required this.mapName,
  });

  factory ExplorationStopResponse.fromJson(Map<String, dynamic> json) {
    return ExplorationStopResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String? ?? '',
      mapSaved: json['map_saved'] as bool? ?? false,
      mapId: json['map_id'] as String?,
      mapName: json['map_name'] as String?,
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String state;
  final bool mapSaved;
  final String? mapId;
  final String? mapName;

  String get message => common.message;
}

class ManualDriveResponse {
  const ManualDriveResponse({
    required this.common,
    required this.accepted,
    required this.command,
    required this.speed,
    required this.state,
  });

  factory ManualDriveResponse.fromJson(Map<String, dynamic> json) {
    return ManualDriveResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      command: json['command'] as String? ?? '',
      speed: (json['speed'] as num?)?.toDouble() ?? 0.0,
      state: json['state'] as String?,
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String command;
  final double speed;
  final String? state;

  String get message => common.message;
}
