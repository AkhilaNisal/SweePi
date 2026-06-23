import 'dart:convert';
import 'dart:io';

import '../models/cleaning_models.dart';
import '../models/exploration_models.dart';
import '../models/map_models.dart';
import '../models/robot_models.dart';

class ApiException implements Exception {
  const ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class RobotApiClient {
  RobotApiClient({
    required this.host,
    required this.apiPort,
  }) : _httpClient = HttpClient();

  final String host;
  final int apiPort;
  final HttpClient _httpClient;

  Uri _uri(String path) => Uri.parse('http://$host:$apiPort$path');

  Future<Map<String, dynamic>> getJson(String path) async {
    final request = await _httpClient.getUrl(_uri(path));
    return _readJsonObject(await request.close());
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final request = await _httpClient.postUrl(_uri(path));
    return _sendJson(request, body);
  }

  Future<Map<String, dynamic>> putJson(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final request = await _httpClient.putUrl(_uri(path));
    return _sendJson(request, body);
  }

  Future<RobotStatus> fetchRobotStatus() async {
    return RobotStatus.fromJson(await getJson('/api/robot/status'));
  }

  Future<ExplorationStartResponse> startExploration({
    required String mapName,
    required String mode,
  }) async {
    final json = await postJson(
      '/api/exploration/start',
      body: {'map_name': mapName, 'mode': mode},
    );
    return ExplorationStartResponse.fromJson(json);
  }

  Future<ExplorationStatus> fetchExplorationStatus() async {
    return ExplorationStatus.fromJson(await getJson('/api/exploration/status'));
  }

  Future<ExplorationStopResponse> stopExploration() async {
    return ExplorationStopResponse.fromJson(
      await postJson('/api/exploration/stop'),
    );
  }

  Future<ManualDriveResponse> sendManualDrive({
    required String command,
    required double speed,
  }) async {
    final json = await postJson(
      '/api/exploration/manual-drive',
      body: {'command': command, 'speed': speed},
    );
    return ManualDriveResponse.fromJson(json);
  }

  Future<List<SweePiMapMetadata>> fetchMaps() async {
    final json = await getJson('/api/maps');
    return ((json['items'] as List?) ?? const [])
        .whereType<Map>()
        .map((item) => SweePiMapMetadata.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  Future<SweePiMapData> fetchMap(String mapId) async {
    return SweePiMapData.fromJson(await getJson('/api/maps/$mapId'));
  }

  Future<SweePiMapMetadata> fetchMapMetadata(String mapId) async {
    return SweePiMapMetadata.fromJson(
      await getJson('/api/maps/$mapId/metadata'),
    );
  }

  Future<SweePiMapMetadata> updateMapMetadata({
    required String mapId,
    required String name,
    required List<MapSection> sections,
  }) async {
    final json = await putJson(
      '/api/maps/$mapId/metadata',
      body: {
        'name': name,
        'sections': sections.map((section) => section.toJson()).toList(),
      },
    );
    return SweePiMapMetadata.fromJson(json);
  }

  Future<CleaningStartResponse> startCleaning({
    required String mapId,
    required List<MapSection> sections,
  }) async {
    final json = await postJson(
      '/api/cleaning/start',
      body: {
        'map_id': mapId,
        'sections': sections.map((section) => section.toJson()).toList(),
      },
    );
    return CleaningStartResponse.fromJson(json);
  }

  Future<SimpleCommandResponse> pauseCleaning() async {
    return SimpleCommandResponse.fromJson(await postJson('/api/cleaning/pause'));
  }

  Future<SimpleCommandResponse> resumeCleaning() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/resume'),
    );
  }

  Future<SimpleCommandResponse> stopCleaning() async {
    return SimpleCommandResponse.fromJson(await postJson('/api/cleaning/stop'));
  }

  Future<void> close() async {
    _httpClient.close();
  }

  Future<Map<String, dynamic>> _sendJson(
    HttpClientRequest request,
    Map<String, dynamic>? body,
  ) async {
    request.headers.contentType = ContentType.json;
    request.write(jsonEncode(body ?? const {}));
    return _readJsonObject(await request.close());
  }

  Future<Map<String, dynamic>> _readJsonObject(HttpClientResponse response) async {
    final body = await response.transform(utf8.decoder).join();
    Map<String, dynamic> payload;

    try {
      final decoded = body.isEmpty ? const <String, dynamic>{} : jsonDecode(body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Expected a JSON object response');
      }
      payload = decoded;
    } on FormatException catch (error) {
      throw ApiException('Invalid JSON from ${response.statusCode}: $error');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = payload['detail'] ?? payload['message'] ?? body;
      throw ApiException('HTTP ${response.statusCode}: $detail');
    }

    return payload;
  }
}
