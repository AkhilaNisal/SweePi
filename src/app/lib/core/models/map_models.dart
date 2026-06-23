class MapSection {
  const MapSection({
    required this.sectionId,
    required this.name,
    required this.polygon,
  });

  factory MapSection.fromJson(Map<String, dynamic> json) {
    final polygon = ((json['polygon'] as List?) ?? const [])
        .whereType<List>()
        .map(
          (point) => point
              .map((value) => (value as num?)?.toDouble() ?? 0.0)
              .toList(),
        )
        .where((point) => point.length >= 2)
        .toList();

    return MapSection(
      sectionId: json['section_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed section',
      polygon: polygon,
    );
  }

  final String sectionId;
  final String name;
  final List<List<double>> polygon;

  Map<String, dynamic> toJson() {
    return {
      'section_id': sectionId,
      'name': name,
      'polygon': polygon,
    };
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
    sections: [],
  );

  final String mapId;
  final String name;
  final String createdAt;
  final String updatedAt;
  final int? width;
  final int? height;
  final double resolution;
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
    required this.width,
    required this.height,
    required this.occupancy,
  });

  factory SweePiMapData.fromJson(Map<String, dynamic> json) {
    return SweePiMapData(
      mapId: json['map_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed map',
      resolution: (json['resolution'] as num?)?.toDouble() ?? 0.05,
      originX: ((json['origin'] as Map?)?['x'] as num?)?.toDouble() ?? 0.0,
      originY: ((json['origin'] as Map?)?['y'] as num?)?.toDouble() ?? 0.0,
      width: (json['width'] as num?)?.toInt() ?? 0,
      height: (json['height'] as num?)?.toInt() ?? 0,
      occupancy: List<int>.from(json['occupancy'] as List? ?? const []),
    );
  }

  static const empty = SweePiMapData(
    mapId: '',
    name: '',
    resolution: 0.05,
    originX: 0,
    originY: 0,
    width: 0,
    height: 0,
    occupancy: [],
  );

  final String mapId;
  final String name;
  final double resolution;
  final double originX;
  final double originY;
  final int width;
  final int height;
  final List<int> occupancy;

  bool get available =>
      mapId.isNotEmpty &&
      width > 0 &&
      height > 0 &&
      occupancy.length >= width * height;
}
