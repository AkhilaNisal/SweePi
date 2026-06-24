import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../models/cleaning_models.dart';
import '../models/exploration_models.dart';
import '../models/map_models.dart';
import '../models/robot_models.dart';

// For a real Android phone, set this to the laptop/robot LAN IP address that
// opens in the phone browser. Do not use localhost, 127.0.0.1, or 0.0.0.0.
const robotIp = '192.168.8.101';
const robotPort = 8080;

class ApiException implements Exception {
  const ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class RobotApiClient {
  RobotApiClient({required this.host, required this.apiPort})
    : _httpClient = HttpClient();

  final String host;
  final int apiPort;
  final HttpClient _httpClient;

  Uri _uri(String path) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri(scheme: 'http', host: host, port: apiPort, path: normalizedPath);
  }

  Future<Map<String, dynamic>> getJson(String path) async {
    final uri = _uri(path);
    _logRequest('GET', uri);
    try {
      final request = await _httpClient.getUrl(uri);
      return _readJsonObject('GET', uri, await request.close());
    } catch (error) {
      if (error is! ApiException) {
        _logError('GET', uri, error);
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path);
    _logRequest('POST', uri, body: body);
    try {
      final request = await _httpClient.postUrl(uri);
      return _sendJson('POST', uri, request, body);
    } catch (error) {
      if (error is! ApiException) {
        _logError('POST', uri, error);
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>> putJson(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path);
    _logRequest('PUT', uri, body: body);
    try {
      final request = await _httpClient.putUrl(uri);
      return _sendJson('PUT', uri, request, body);
    } catch (error) {
      if (error is! ApiException) {
        _logError('PUT', uri, error);
      }
      rethrow;
    }
  }

  Future<RobotStatus> fetchRobotStatus() async {
    return RobotStatus.fromJson(await getJson('/api/robot/status'));
  }

  Future<Map<String, dynamic>> fetchHealth() async {
    return getJson('/api/system/health');
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

  Future<ExplorationSwitchResponse> switchExplorationMode({
    required String newMode,
  }) async {
    final json = await postJson(
      '/api/exploration/switch',
      body: {'new_mode': newMode},
    );
    return ExplorationSwitchResponse.fromJson(json);
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
    required String cleaningMode,
    required List<MapSection> sections,
    SweePiMapData? processedMap,
    required RobotPose initialPose,
  }) async {
    final body = buildCleaningStartRequestBody(
      mapId: mapId,
      cleaningMode: cleaningMode,
      sections: sections,
      processedMap: processedMap,
      initialPose: initialPose,
    );

    final json = await postJson('/api/cleaning/start', body: body);
    return CleaningStartResponse.fromJson(json);
  }

  Future<CleaningStatus> fetchCleaningStatus() async {
    return CleaningStatus.fromJson(await getJson('/api/cleaning/status'));
  }

  Future<SimpleCommandResponse> pauseCleaning() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/pause'),
    );
  }

  Future<SimpleCommandResponse> resumeCleaning() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/resume'),
    );
  }

  Future<SimpleCommandResponse> stopCleaning() async {
    return SimpleCommandResponse.fromJson(await postJson('/api/cleaning/stop'));
  }

  Future<SimpleCommandResponse> resetCleaning() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/reset'),
    );
  }

  Future<SimpleCommandResponse> returnHome() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/return-home'),
    );
  }

  Future<void> close() async {
    _httpClient.close();
  }

  Future<Map<String, dynamic>> _sendJson(
    String method,
    Uri uri,
    HttpClientRequest request,
    Map<String, dynamic>? body,
  ) async {
    request.headers.contentType = ContentType.json;
    request.write(jsonEncode(body ?? const {}));
    return _readJsonObject(method, uri, await request.close());
  }

  Future<Map<String, dynamic>> _readJsonObject(
    String method,
    Uri uri,
    HttpClientResponse response,
  ) async {
    final body = await response.transform(utf8.decoder).join();
    _logResponse(method, uri, response.statusCode, body);
    Map<String, dynamic> payload;

    try {
      final decoded = body.isEmpty
          ? const <String, dynamic>{}
          : jsonDecode(body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Expected a JSON object response');
      }
      payload = decoded;
    } on FormatException catch (error) {
      throw ApiException('Invalid JSON from ${response.statusCode}: $error');
    }

    if (response.statusCode < 200 ||
        response.statusCode >= 300 ||
        payload['success'] == false) {
      final detail = payload['message'] ?? payload['detail'] ?? body;
      final code = payload['error'] is Map
          ? (payload['error'] as Map)['code'] as String?
          : null;
      throw ApiException(
        code == null
            ? 'HTTP ${response.statusCode}: $detail'
            : 'HTTP ${response.statusCode}: $detail ($code)',
      );
    }

    return payload;
  }

  void _logRequest(String method, Uri uri, {Map<String, dynamic>? body}) {
    if (!kDebugMode) {
      return;
    }
    debugPrint('[RobotApiClient] -> $method $uri');
    if (body != null) {
      debugPrint('[RobotApiClient] -> body ${jsonEncode(body)}');
    }
  }

  void _logResponse(String method, Uri uri, int statusCode, String body) {
    if (!kDebugMode) {
      return;
    }
    debugPrint('[RobotApiClient] <- $method $uri $statusCode');
    if (body.isNotEmpty) {
      debugPrint('[RobotApiClient] <- body $body');
    }
  }

  void _logError(String method, Uri uri, Object error) {
    if (!kDebugMode) {
      return;
    }
    debugPrint('[RobotApiClient] !! $method $uri $error');
  }
}

Map<String, dynamic> buildCleaningStartRequestBody({
  required String mapId,
  required String cleaningMode,
  required List<MapSection> sections,
  SweePiMapData? processedMap,
  required RobotPose initialPose,
}) {
  final body = <String, dynamic>{
    'map_id': mapId,
    'cleaning_mode': cleaningMode,
    'sections': sections.map((section) => section.toJson()).toList(),
    'initial_pose': initialPose.toJson(),
  };
  if (processedMap != null) {
    body['processed_map'] = processedMap.toProcessedMapJson();
  }
  return body;
}
