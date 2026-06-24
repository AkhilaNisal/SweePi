class SectionBounds {
  const SectionBounds({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
  });

  factory SectionBounds.fromJson(Map<String, dynamic> json) {
    return SectionBounds(
      x: (json['x'] as num?)?.toDouble() ?? 0,
      y: (json['y'] as num?)?.toDouble() ?? 0,
      width: (json['width'] as num?)?.toDouble() ?? 0,
      height: (json['height'] as num?)?.toDouble() ?? 0,
    );
  }

  final double x;
  final double y;
  final double width;
  final double height;

  bool get isValid => width > 0 && height > 0;

  Map<String, dynamic> toJson() {
    return {'x': x, 'y': y, 'width': width, 'height': height};
  }
}

class MapSection {
  const MapSection({
    required this.sectionId,
    required this.name,
    required this.bounds,
  });

  factory MapSection.fromJson(Map<String, dynamic> json) {
    final boundsJson = json['bounds'];
    return MapSection(
      sectionId: json['section_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed section',
      bounds: boundsJson is Map
          ? SectionBounds.fromJson(boundsJson.cast<String, dynamic>())
          : const SectionBounds(x: 0, y: 0, width: 0, height: 0),
    );
  }

  final String sectionId;
  final String name;
  final SectionBounds bounds;

  Map<String, dynamic> toJson() {
    return {'section_id': sectionId, 'name': name, 'bounds': bounds.toJson()};
  }
}

class SweePiMapMetadata {
  const SweePiMapMetadata({
    required this.mapId,
    required this.name,
    required this.createdAt,
    required this.updatedAt,
    required this.width,
    required this.height,
    required this.resolution,
    required this.originX,
    required this.originY,
    required this.originYaw,
    required this.sections,
  });

  factory SweePiMapMetadata.fromJson(Map<String, dynamic> json) {
    return SweePiMapMetadata(
      mapId: json['map_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed map',
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String? ?? '',
      width: (json['width'] as num?)?.toInt(),
      height: (json['height'] as num?)?.toInt(),
      resolution: (json['resolution'] as num?)?.toDouble() ?? 0.05,
      originX: ((json['origin'] as Map?)?['x'] as num?)?.toDouble() ?? 0.0,
      originY: ((json['origin'] as Map?)?['y'] as num?)?.toDouble() ?? 0.0,
      originYaw: ((json['origin'] as Map?)?['yaw'] as num?)?.toDouble() ?? 0.0,
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
    );
  }

  static const empty = SweePiMapMetadata(
    mapId: '',
    name: '',
    createdAt: '',
    updatedAt: '',
    width: null,
    height: null,
    resolution: 0.05,
    originX: 0,
    originY: 0,
    originYaw: 0,
    sections: [],
  );

  final String mapId;
  final String name;
  final String createdAt;
  final String updatedAt;
  final int? width;
  final int? height;
  final double resolution;
  final double originX;
  final double originY;
  final double originYaw;
  final List<MapSection> sections;

  SweePiMapMetadata copyWith({
    String? name,
    String? updatedAt,
    List<MapSection>? sections,
  }) {
    return SweePiMapMetadata(
      mapId: mapId,
      name: name ?? this.name,
      createdAt: createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      width: width,
      height: height,
      resolution: resolution,
      originX: originX,
      originY: originY,
      originYaw: originYaw,
      sections: sections ?? this.sections,
    );
  }
}

class SweePiMapData {
  const SweePiMapData({
    required this.mapId,
    required this.name,
    required this.resolution,
    required this.originX,
    required this.originY,
    this.originYaw = 0,
    required this.width,
    required this.height,
    required this.occupancy,
    this.sections = const [],
  });

  factory SweePiMapData.fromJson(Map<String, dynamic> json) {
    return SweePiMapData(
      mapId: json['map_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed map',
      resolution: (json['resolution'] as num?)?.toDouble() ?? 0.05,
      originX: ((json['origin'] as Map?)?['x'] as num?)?.toDouble() ?? 0.0,
      originY: ((json['origin'] as Map?)?['y'] as num?)?.toDouble() ?? 0.0,
      originYaw: ((json['origin'] as Map?)?['yaw'] as num?)?.toDouble() ?? 0.0,
      width: (json['width'] as num?)?.toInt() ?? 0,
      height: (json['height'] as num?)?.toInt() ?? 0,
      occupancy: List<int>.from(json['occupancy'] as List? ?? const []),
      sections: ((json['sections'] as List?) ?? const [])
          .whereType<Map>()
          .map((item) => MapSection.fromJson(item.cast<String, dynamic>()))
          .toList(),
    );
  }

  static const empty = SweePiMapData(
    mapId: '',
    name: '',
    resolution: 0.05,
    originX: 0,
    originY: 0,
    originYaw: 0,
    width: 0,
    height: 0,
    occupancy: [],
    sections: [],
  );

  final String mapId;
  final String name;
  final double resolution;
  final double originX;
  final double originY;
  final double originYaw;
  final int width;
  final int height;
  final List<int> occupancy;
  final List<MapSection> sections;

  bool get available =>
      mapId.isNotEmpty &&
      width > 0 &&
      height > 0 &&
      occupancy.length >= width * height;

  SweePiMapData copyWith({
    String? mapId,
    String? name,
    double? resolution,
    double? originX,
    double? originY,
    double? originYaw,
    int? width,
    int? height,
    List<int>? occupancy,
    List<MapSection>? sections,
  }) {
    return SweePiMapData(
      mapId: mapId ?? this.mapId,
      name: name ?? this.name,
      resolution: resolution ?? this.resolution,
      originX: originX ?? this.originX,
      originY: originY ?? this.originY,
      originYaw: originYaw ?? this.originYaw,
      width: width ?? this.width,
      height: height ?? this.height,
      occupancy: occupancy ?? this.occupancy,
      sections: sections ?? this.sections,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'map_id': mapId,
      'name': name,
      'resolution': resolution,
      'origin': {'x': originX, 'y': originY, 'yaw': originYaw},
      'width': width,
      'height': height,
      'occupancy': occupancy,
      'sections': sections.map((section) => section.toJson()).toList(),
    };
  }

  Map<String, dynamic> toProcessedMapJson() {
    return {
      'width': width,
      'height': height,
      'resolution': resolution,
      'origin': {'x': originX, 'y': originY, 'yaw': originYaw},
      'occupancy': occupancy,
    };
  }
}
