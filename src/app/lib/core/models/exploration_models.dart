class ExplorationStatus {
  const ExplorationStatus({
    required this.state,
    required this.mode,
    required this.mapName,
    required this.mapAvailable,
    required this.message,
  });

  factory ExplorationStatus.fromJson(Map<String, dynamic> json) {
    return ExplorationStatus(
      state: json['state'] as String? ?? 'unknown',
      mode: json['mode'] as String? ?? 'automatic',
      mapName: json['map_name'] as String?,
      mapAvailable: json['map_available'] as bool? ?? false,
      message: json['message'] as String? ?? '',
    );
  }

  static const empty = ExplorationStatus(
    state: 'idle',
    mode: 'automatic',
    mapName: null,
    mapAvailable: false,
    message: 'Exploration status has not been loaded.',
  );

  final String state;
  final String mode;
  final String? mapName;
  final bool mapAvailable;
  final String message;
}

class ExplorationStartResponse {
  const ExplorationStartResponse({
    required this.accepted,
    required this.state,
    required this.mode,
    required this.mapName,
    required this.message,
  });

  factory ExplorationStartResponse.fromJson(Map<String, dynamic> json) {
    return ExplorationStartResponse(
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String? ?? '',
      mode: json['mode'] as String? ?? 'automatic',
      mapName: json['map_name'] as String? ?? '',
      message: json['message'] as String? ?? '',
    );
  }

  final bool accepted;
  final String state;
  final String mode;
  final String mapName;
  final String message;
}

class ExplorationStopResponse {
  const ExplorationStopResponse({
    required this.accepted,
    required this.state,
    required this.mapSaved,
    required this.mapId,
    required this.message,
  });

  factory ExplorationStopResponse.fromJson(Map<String, dynamic> json) {
    return ExplorationStopResponse(
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String? ?? '',
      mapSaved: json['map_saved'] as bool? ?? false,
      mapId: json['map_id'] as String?,
      message: json['message'] as String? ?? '',
    );
  }

  final bool accepted;
  final String state;
  final bool mapSaved;
  final String? mapId;
  final String message;
}

class ManualDriveResponse {
  const ManualDriveResponse({
    required this.accepted,
    required this.command,
    required this.speed,
    required this.message,
  });

  factory ManualDriveResponse.fromJson(Map<String, dynamic> json) {
    return ManualDriveResponse(
      accepted: json['accepted'] as bool? ?? false,
      command: json['command'] as String? ?? '',
      speed: (json['speed'] as num?)?.toDouble() ?? 0.0,
      message: json['message'] as String? ?? '',
    );
  }

  final bool accepted;
  final String command;
  final double speed;
  final String message;
}
