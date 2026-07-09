import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../connection/robot_discovered_device.dart';
import '../models/cleaning_models.dart';
import '../models/exploration_models.dart';
import '../models/map_models.dart';
import '../models/robot_models.dart';

// For a real Android phone, set this to the laptop/robot LAN IP address that
// opens in the phone browser. Do not use localhost, 127.0.0.1, or 0.0.0.0.
const robotIp = '192.168.8.101';
const robotPort = 8080;
const robotApiRequestTimeout = Duration(seconds: 8);

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
    this.websocketPort = 8765,
  }) : _httpClient = HttpClient() {
    _httpClient.connectionTimeout = robotApiRequestTimeout;
  }

  factory RobotApiClient.fromDiscoveredRobot(RobotDiscoveredDevice robot) {
    final host = robot.bestHost;
    if (host == null || host.isEmpty) {
      throw ApiException('No Wi-Fi address was resolved for ${robot.name}.');
    }
    return RobotApiClient(
      host: host,
      apiPort: robot.apiPort,
      websocketPort: robot.websocketPort,
    );
  }

  factory RobotApiClient.fromBaseUri(Uri baseUri, {int websocketPort = 8765}) {
    return RobotApiClient(
      host: baseUri.host,
      apiPort: baseUri.port == 0 ? robotPort : baseUri.port,
      websocketPort: websocketPort,
    );
  }

  final String host;
  final int apiPort;
  final int websocketPort;
  final HttpClient _httpClient;

  Uri get baseUri => Uri(scheme: 'http', host: host, port: apiPort);
  Uri get websocketUri => Uri(scheme: 'ws', host: host, port: websocketPort);

  Uri _uri(String path) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri(scheme: 'http', host: host, port: apiPort, path: normalizedPath);
  }

  Future<Map<String, dynamic>> getJson(String path) async {
    final uri = _uri(path);
    _logRequest('GET', uri);
    try {
      final request = await _httpClient
          .getUrl(uri)
          .timeout(robotApiRequestTimeout);
      return _readJsonObject(
        'GET',
        uri,
        await request.close().timeout(robotApiRequestTimeout),
      );
    } catch (error) {
      if (error is! ApiException) {
        _logError('GET', uri, error);
      }
      if (isApiConnectivityFailure(error)) {
        throw ApiException(apiConnectivityTroubleshootingMessage(uri));
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
      final request = await _httpClient
          .postUrl(uri)
          .timeout(robotApiRequestTimeout);
      return _sendJson('POST', uri, request, body);
    } catch (error) {
      if (error is! ApiException) {
        _logError('POST', uri, error);
      }
      if (isApiConnectivityFailure(error)) {
        throw ApiException(apiConnectivityTroubleshootingMessage(uri));
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
      final request = await _httpClient
          .putUrl(uri)
          .timeout(robotApiRequestTimeout);
      return _sendJson('PUT', uri, request, body);
    } catch (error) {
      if (error is! ApiException) {
        _logError('PUT', uri, error);
      }
      if (isApiConnectivityFailure(error)) {
        throw ApiException(apiConnectivityTroubleshootingMessage(uri));
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
  }) async {
    final body = buildCleaningStartRequestBody(
      mapId: mapId,
      cleaningMode: cleaningMode,
      sections: sections,
      processedMap: processedMap,
    );

    final json = await postJson('/api/cleaning/start', body: body);
    return CleaningStartResponse.fromJson(json);
  }

  Future<SimpleCommandResponse> setCleaningInitialPose({
    required String mapId,
    required RobotPose initialPose,
  }) async {
    final json = await postJson(
      '/api/localization/initial-pose',
      body: buildInitialPoseRequestBody(mapId: mapId, initialPose: initialPose),
    );
    return SimpleCommandResponse.fromJson(json);
  }

  Future<SimpleCommandResponse> validateCleaning() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/validate'),
    );
  }

  Future<SimpleCommandResponse> startCleaningMotion() async {
    return SimpleCommandResponse.fromJson(
      await postJson('/api/cleaning/start-motion'),
    );
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
    final bodyText = jsonEncode(body ?? const <String, dynamic>{});
    final bodyBytes = utf8.encode(bodyText);

    request.headers.contentType = ContentType(
      'application',
      'json',
      charset: 'utf-8',
    );

    request.headers.set(HttpHeaders.acceptHeader, 'application/json');

    // Important: force Content-Length instead of Transfer-Encoding: chunked
    request.contentLength = bodyBytes.length;

    request.add(bodyBytes);

    return _readJsonObject(
      method,
      uri,
      await request.close().timeout(robotApiRequestTimeout),
    );
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

@visibleForTesting
bool isApiConnectivityFailure(Object error) {
  if (error is SocketException || error is TimeoutException) {
    return true;
  }
  final message = error.toString().toLowerCase();
  return message.contains('connection refused') ||
      message.contains('connection timed out') ||
      message.contains('timed out');
}

@visibleForTesting
String apiConnectivityTroubleshootingMessage(Uri attemptedUri) {
  final healthUri = Uri(
    scheme: attemptedUri.scheme,
    host: attemptedUri.host,
    port: attemptedUri.port,
    path: '/api/system/health',
  );
  return 'Could not reach SweePi over Wi-Fi. Make sure your phone is '
      'connected to the same Wi-Fi/hotspot as SweePi, and make sure the '
      'Raspberry Pi API bridge is running:\n\n'
      'ros2 launch sweepi_api_bridge api_bridge.launch.py\n\n'
      'You can test it from your phone browser:\n'
      '$healthUri';
}

Map<String, dynamic> buildCleaningStartRequestBody({
  required String mapId,
  required String cleaningMode,
  required List<MapSection> sections,
  SweePiMapData? processedMap,
}) {
  final body = <String, dynamic>{
    'map_id': mapId,
    'cleaning_mode': cleaningMode,
    'sections': sections.map((section) => section.toJson()).toList(),
  };
  if (processedMap != null) {
    body['processed_map'] = processedMap.toProcessedMapJson();
  }
  return body;
}

Map<String, dynamic> buildInitialPoseRequestBody({
  required String mapId,
  required RobotPose initialPose,
}) {
  return {
    'map_id': mapId,
    'x': initialPose.x,
    'y': initialPose.y,
    'yaw': initialPose.yaw,
    'frame': initialPose.frame,
  };
}
