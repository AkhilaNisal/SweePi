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

class CommandLifecycleFields {
  const CommandLifecycleFields({
    required this.accepted,
    required this.completed,
    required this.taskFinished,
    required this.taskResult,
    required this.command,
    required this.state,
    required this.nextSteps,
  });

  factory CommandLifecycleFields.fromJson(Map<String, dynamic> json) {
    return CommandLifecycleFields(
      accepted: json['accepted'] as bool? ?? false,
      completed: json['completed'] as bool? ?? false,
      taskFinished: json['task_finished'] as bool? ?? false,
      taskResult: json['task_result'] as String?,
      command: json['command'] as String?,
      state: json['state'] as String?,
      nextSteps: List<String>.from(json['next_steps'] as List? ?? const []),
    );
  }

  final bool accepted;
  final bool completed;
  final bool taskFinished;
  final String? taskResult;
  final String? command;
  final String? state;
  final List<String> nextSteps;
}

class CleaningStartResponse {
  const CleaningStartResponse({
    required this.common,
    required this.lifecycle,
    required this.taskId,
    required this.mapId,
    required this.cleaningMode,
    required this.sections,
    required this.initialPose,
    required this.initialPoseRequired,
    required this.progressPercent,
  });

  factory CleaningStartResponse.fromJson(Map<String, dynamic> json) {
    return CleaningStartResponse(
      common: ApiResponseFields.fromJson(json),
      lifecycle: CommandLifecycleFields.fromJson(json),
      taskId: json['task_id'] as String?,
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
      initialPoseRequired: json['initial_pose_required'] as bool? ?? false,
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final ApiResponseFields common;
  final CommandLifecycleFields lifecycle;
  final String? taskId;
  final String? mapId;
  final String? cleaningMode;
  final List<MapSection> sections;
  final RobotPose? initialPose;
  final bool initialPoseRequired;
  final double progressPercent;

  bool get accepted => lifecycle.accepted;
  bool get completed => lifecycle.completed;
  bool get commandSucceeded =>
      common.success && lifecycle.accepted && lifecycle.completed;
  String get state => lifecycle.state ?? '';
  String get message => common.message;
  List<String> get nextSteps => lifecycle.nextSteps;
}

class CleaningStatus {
  const CleaningStatus({
    required this.common,
    required this.active,
    required this.state,
    required this.taskId,
    required this.mapId,
    required this.coverageMapId,
    required this.cleaningMode,
    required this.sections,
    required this.progressPercent,
    required this.pose,
    required this.paused,
    required this.initialPoseReceived,
    required this.initialPoseConfirmed,
    required this.initialPoseSource,
    required this.poseAvailable,
    required this.coveragePathAvailable,
    required this.pathAvailable,
    required this.coverageMapAvailable,
    required this.coverageValidated,
    required this.readyToValidate,
    required this.readyToStartMotion,
    required this.taskFinished,
    required this.taskResult,
    required this.lastError,
    required this.nextSteps,
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
      coverageMapId: json['coverage_map_id'] as String?,
      cleaningMode: json['cleaning_mode'] as String?,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
      pose: json['pose'] is Map
          ? RobotPose.fromJson((json['pose'] as Map).cast<String, dynamic>())
          : null,
      paused: json['paused'] as bool? ?? false,
      initialPoseReceived: json['initial_pose_received'] as bool? ?? false,
      initialPoseConfirmed: json['initial_pose_confirmed'] as bool? ?? false,
      initialPoseSource: json['initial_pose_source'] as String?,
      poseAvailable: json['pose_available'] as bool? ?? false,
      coveragePathAvailable: json['coverage_path_available'] as bool? ?? false,
      pathAvailable: json['path_available'] as bool? ?? false,
      coverageMapAvailable: json['coverage_map_available'] as bool? ?? false,
      coverageValidated: json['coverage_validated'] as bool? ?? false,
      readyToValidate: json['ready_to_validate'] as bool? ?? false,
      readyToStartMotion: json['ready_to_start_motion'] as bool? ?? false,
      taskFinished: json['task_finished'] as bool? ?? false,
      taskResult: json['task_result'] as String?,
      lastError: _stringFromOptional(json['last_error']),
      nextSteps: List<String>.from(json['next_steps'] as List? ?? const []),
      navExecutionStatus: nav is Map
          ? nav['execution_status'] as String? ?? 'IDLE'
          : 'IDLE',
    );
  }

  static const empty = CleaningStatus(
    common: ApiResponseFields(
      success: true,
      message: 'Cleaning status has not been loaded.',
      error: null,
      timestamp: null,
    ),
    active: false,
    state: 'idle',
    taskId: null,
    mapId: null,
    coverageMapId: null,
    cleaningMode: null,
    sections: [],
    progressPercent: 0,
    pose: null,
    paused: false,
    initialPoseReceived: false,
    initialPoseConfirmed: false,
    initialPoseSource: null,
    poseAvailable: false,
    coveragePathAvailable: false,
    pathAvailable: false,
    coverageMapAvailable: false,
    coverageValidated: false,
    readyToValidate: false,
    readyToStartMotion: false,
    taskFinished: false,
    taskResult: null,
    lastError: null,
    nextSteps: [],
    navExecutionStatus: 'IDLE',
  );

  final ApiResponseFields common;
  final bool active;
  final String state;
  final String? taskId;
  final String? mapId;
  final String? coverageMapId;
  final String? cleaningMode;
  final List<MapSection> sections;
  final double progressPercent;
  final RobotPose? pose;
  final bool paused;
  final bool initialPoseReceived;
  final bool initialPoseConfirmed;
  final String? initialPoseSource;
  final bool poseAvailable;
  final bool coveragePathAvailable;
  final bool pathAvailable;
  final bool coverageMapAvailable;
  final bool coverageValidated;
  final bool readyToValidate;
  final bool readyToStartMotion;
  final bool taskFinished;
  final String? taskResult;
  final String? lastError;
  final List<String> nextSteps;
  final String navExecutionStatus;

  String get message => common.message;
}

class SimpleCommandResponse {
  const SimpleCommandResponse({
    required this.common,
    required this.lifecycle,
    required this.taskId,
    required this.mapId,
    required this.coverageMapId,
    required this.initialPoseReceived,
    required this.initialPoseConfirmed,
    required this.initialPoseSource,
    required this.initialPose,
  });

  factory SimpleCommandResponse.fromJson(Map<String, dynamic> json) {
    return SimpleCommandResponse(
      common: ApiResponseFields.fromJson(json),
      lifecycle: CommandLifecycleFields.fromJson(json),
      taskId: json['task_id'] as String?,
      mapId: json['map_id'] as String?,
      coverageMapId: json['coverage_map_id'] as String?,
      initialPoseReceived: json['initial_pose_received'] as bool? ?? false,
      initialPoseConfirmed: json['initial_pose_confirmed'] as bool? ?? false,
      initialPoseSource: json['initial_pose_source'] as String?,
      initialPose: json['initial_pose'] is Map
          ? RobotPose.fromJson(
              (json['initial_pose'] as Map).cast<String, dynamic>(),
            )
          : null,
    );
  }

  final ApiResponseFields common;
  final CommandLifecycleFields lifecycle;
  final String? taskId;
  final String? mapId;
  final String? coverageMapId;
  final bool initialPoseReceived;
  final bool initialPoseConfirmed;
  final String? initialPoseSource;
  final RobotPose? initialPose;

  bool get accepted => lifecycle.accepted;
  bool get completed => lifecycle.completed;
  bool get commandSucceeded =>
      common.success && lifecycle.accepted && lifecycle.completed;
  String? get command => lifecycle.command;
  String? get state => lifecycle.state;
  String get message => common.message;
  List<String> get nextSteps => lifecycle.nextSteps;
}

String? _stringFromOptional(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is String) {
    return value;
  }
  if (value is Map) {
    final message = value['message'] ?? value['code'];
    return message?.toString();
  }
  return value.toString();
}
