import 'map_models.dart';

class CleaningStartResponse {
  const CleaningStartResponse({
    required this.accepted,
    required this.taskId,
    required this.state,
    required this.mapId,
    required this.sections,
    required this.message,
  });

  factory CleaningStartResponse.fromJson(Map<String, dynamic> json) {
    return CleaningStartResponse(
      accepted: json['accepted'] as bool? ?? false,
      taskId: json['task_id'] as String?,
      state: json['state'] as String? ?? '',
      mapId: json['map_id'] as String?,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
      message: json['message'] as String? ?? '',
    );
  }

  final bool accepted;
  final String? taskId;
  final String state;
  final String? mapId;
  final List<MapSection> sections;
  final String message;
}

class SimpleCommandResponse {
  const SimpleCommandResponse({
    required this.accepted,
    required this.state,
    required this.message,
  });

  factory SimpleCommandResponse.fromJson(Map<String, dynamic> json) {
    return SimpleCommandResponse(
      accepted: json['accepted'] as bool? ?? false,
      state: json['state'] as String?,
      message: json['message'] as String? ?? '',
    );
  }

  final bool accepted;
  final String? state;
  final String message;
}
