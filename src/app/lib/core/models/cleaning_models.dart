import 'map_models.dart';
import 'robot_models.dart';

class ApiErrorBody {
  const ApiErrorBody({required this.code, required this.details});

  factory ApiErrorBody.fromJson(Map<String, dynamic> json) {
    return ApiErrorBody(
      code: json['code'] as String? ?? '',
      details: json['details'] is Map
          ? (json['details'] as Map).cast<String, dynamic>()
          : const {},
    );
  }

  final String code;
  final Map<String, dynamic> details;
}

class ApiResponseFields {
  const ApiResponseFields({
    required this.success,
    required this.message,
    required this.error,
    required this.timestamp,
  });

  factory ApiResponseFields.fromJson(Map<String, dynamic> json) {
    final error = json['error'];
    return ApiResponseFields(
      success: json['success'] as bool? ?? true,
      message: json['message'] as String? ?? '',
      error: error is Map
          ? ApiErrorBody.fromJson(error.cast<String, dynamic>())
          : null,
      timestamp: json['timestamp'] as String?,
    );
  }

  final bool success;
  final String message;
  final ApiErrorBody? error;
  final String? timestamp;
}

class CleaningStartResponse {
  const CleaningStartResponse({
    required this.common,
    required this.accepted,
    required this.taskId,
    required this.state,
    required this.mapId,
    required this.cleaningMode,
    required this.sections,
    required this.initialPose,
    required this.progressPercent,
  });

  factory CleaningStartResponse.fromJson(Map<String, dynamic> json) {
    return CleaningStartResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      taskId: json['task_id'] as String?,
      state: json['state'] as String? ?? '',
      mapId: json['map_id'] as String?,
      cleaningMode: json['cleaning_mode'] as String?,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
      initialPose: json['initial_pose'] is Map
          ? RobotPose.fromJson(
              (json['initial_pose'] as Map).cast<String, dynamic>(),
            )
          : null,
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String? taskId;
  final String state;
  final String? mapId;
  final String? cleaningMode;
  final List<MapSection> sections;
  final RobotPose? initialPose;
  final double progressPercent;

  String get message => common.message;
}

class CleaningStatus {
  const CleaningStatus({
    required this.common,
    required this.active,
    required this.state,
    required this.taskId,
    required this.mapId,
    required this.cleaningMode,
    required this.sections,
    required this.progressPercent,
    required this.pose,
    required this.navExecutionStatus,
  });

  factory CleaningStatus.fromJson(Map<String, dynamic> json) {
    final nav = json['nav'];
    return CleaningStatus(
      common: ApiResponseFields.fromJson(json),
      active: json['active'] as bool? ?? false,
      state: json['state'] as String? ?? 'idle',
      taskId: json['task_id'] as String?,
      mapId: json['map_id'] as String?,
      cleaningMode: json['cleaning_mode'] as String?,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
      pose: json['pose'] is Map
          ? RobotPose.fromJson((json['pose'] as Map).cast<String, dynamic>())
          : null,
      navExecutionStatus: nav is Map
          ? nav['execution_status'] as String? ?? 'IDLE'
          : 'IDLE',
    );
  }

  final ApiResponseFields common;
  final bool active;
  final String state;
  final String? taskId;
  final String? mapId;
  final String? cleaningMode;
  final List<MapSection> sections;
  final double progressPercent;
  final RobotPose? pose;
  final String navExecutionStatus;

  String get message => common.message;
}

class SimpleCommandResponse {
  const SimpleCommandResponse({
    required this.common,
    required this.accepted,
    required this.state,
    required this.taskId,
  });

  factory SimpleCommandResponse.fromJson(Map<String, dynamic> json) {
    return SimpleCommandResponse(
      common: ApiResponseFields.fromJson(json),
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String?,
      taskId: json['task_id'] as String?,
    );
  }

  final ApiResponseFields common;
  final bool accepted;
  final String? state;
  final String? taskId;

  String get message => common.message;
}
