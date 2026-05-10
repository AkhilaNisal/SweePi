import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';

import '../../core/models/robot_models.dart';
import '../../core/network/robot_api_client.dart';

class AppController extends ChangeNotifier {
  String host = '192.168.0.10';
  int apiPort = 8080;
  int wsPort = 8765;

  bool isConnected = false;
  bool isBusy = false;
  String? errorMessage;
  RobotStatus status = RobotStatus.offline;
  MapPayload mapPayload = MapPayload.empty;
  List<ScheduleItem> schedules = const [];
  List<HistoryItem> history = const [];

  RectSelection? pendingSelection;

  RobotApiClient? _client;
  StreamSubscription<Map<String, dynamic>>? _socketSubscription;

  Future<void> connect() async {
    await disconnect();
    isBusy = true;
    errorMessage = null;
    notifyListeners();

    try {
      _client = RobotApiClient(host: host, apiPort: apiPort, wsPort: wsPort);
      await refreshAll();
      _socketSubscription = _client!.connectWebSocket().listen(_handleSocketEvent);
      isConnected = true;
    } catch (error) {
      errorMessage = '$error';
      isConnected = false;
      status = RobotStatus.offline;
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> disconnect() async {
    await _socketSubscription?.cancel();
    _socketSubscription = null;
    await _client?.close();
    _client = null;
    isConnected = false;
    notifyListeners();
  }

  Future<void> refreshAll() async {
    if (_client == null) {
      return;
    }
    final statusJson = await _client!.getJson('/api/v1/robot/status');
    final mapJson = await _client!.getJson('/api/v1/maps/current');
    final schedulesJson = await _client!.getJson('/api/v1/schedules');
    final historyJson = await _client!.getJson('/api/v1/history');

    status = RobotStatus.fromJson(statusJson);
    mapPayload = MapPayload.fromJson(mapJson);
    schedules = ((schedulesJson['items'] as List?) ?? const [])
        .map((item) => ScheduleItem.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
    history = ((historyJson['items'] as List?) ?? const [])
        .map((item) => HistoryItem.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
    notifyListeners();
  }

  Future<void> sendCommand(String path, {Map<String, dynamic>? body}) async {
    if (_client == null) {
      return;
    }
    isBusy = true;
    errorMessage = null;
    notifyListeners();
    try {
      final response = await _client!.sendJson('POST', path, body: body);
      if (response['accepted'] == false) {
        errorMessage = response['message'] as String? ?? 'Command rejected';
      }
      await refreshAll();
    } catch (error) {
      errorMessage = '$error';
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> saveSelection() async {
    if (_client == null || pendingSelection == null || !mapPayload.available) {
      return;
    }
    final payload = {
      'map_id': mapPayload.mapId,
      'map_revision': mapPayload.revision,
      'zones': [
        {
          'id': 'zone_${DateTime.now().millisecondsSinceEpoch}',
          'polygon': pendingSelection!.toWorldPolygon(mapPayload),
        }
      ],
      'no_go_zones': const [],
      'room_ids': const [],
    };
    isBusy = true;
    notifyListeners();
    try {
      await _client!.sendJson('PUT', '/api/v1/cleaning/selection', body: payload);
      await refreshAll();
    } catch (error) {
      errorMessage = '$error';
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> startSelectedCleaning() async {
    await sendCommand('/api/v1/cleaning/start-selected', body: const {});
  }

  Future<void> saveSchedule({
    required String id,
    required String timeLocal,
    required List<String> days,
  }) async {
    if (_client == null) {
      return;
    }
    final selection = {
      'room_ids': status.selection['room_ids'] ?? const [],
      'zones': status.selection['zones'] ?? const [],
      'no_go_zones': status.selection['no_go_zones'] ?? const [],
    };
    final body = {
      'id': id,
      'enabled': true,
      'timezone': 'Asia/Colombo',
      'time_local': timeLocal,
      'days': days,
      'map_id': mapPayload.mapId,
      'selection': selection,
    };
    final method = schedules.any((item) => item.id == id) ? 'PUT' : 'POST';
    try {
      if (method == 'POST') {
        await _client!.sendJson(method, '/api/v1/schedules', body: body);
      } else {
        await _client!.sendJson(method, '/api/v1/schedules/$id', body: body);
      }
      await refreshAll();
    } catch (error) {
      errorMessage = '$error';
      notifyListeners();
    }
  }

  Future<void> deleteSchedule(String id) async {
    if (_client == null) {
      return;
    }
    await _client!.sendJson('DELETE', '/api/v1/schedules/$id');
    await refreshAll();
  }

  void updateHost(String value) {
    host = value;
    notifyListeners();
  }

  void updateApiPort(String value) {
    apiPort = int.tryParse(value) ?? apiPort;
    notifyListeners();
  }

  void updateWsPort(String value) {
    wsPort = int.tryParse(value) ?? wsPort;
    notifyListeners();
  }

  void setPendingSelection(RectSelection? selection) {
    pendingSelection = selection;
    notifyListeners();
  }

  void _handleSocketEvent(Map<String, dynamic> event) {
    final type = event['type'] as String? ?? '';
    final payload = (event['payload'] as Map?)?.cast<String, dynamic>() ?? const {};
    if (type == 'status.snapshot' || type == 'status.update') {
      status = RobotStatus.fromJson(payload);
    }
    if (type == 'map.updated') {
      unawaited(_refreshMapOnly());
    }
    unawaited(_refreshHistoryOnly());
    notifyListeners();
  }

  Future<void> _refreshMapOnly() async {
    if (_client == null) {
      return;
    }
    final mapJson = await _client!.getJson('/api/v1/maps/current');
    mapPayload = MapPayload.fromJson(mapJson);
    notifyListeners();
  }

  Future<void> _refreshHistoryOnly() async {
    if (_client == null) {
      return;
    }
    final historyJson = await _client!.getJson('/api/v1/history');
    history = ((historyJson['items'] as List?) ?? const [])
        .map((item) => HistoryItem.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
    notifyListeners();
  }
}

class RectSelection {
  const RectSelection({
    required this.left,
    required this.top,
    required this.right,
    required this.bottom,
  });

  final double left;
  final double top;
  final double right;
  final double bottom;

  RectSelection normalized() {
    return RectSelection(
      left: math.min(left, right),
      top: math.min(top, bottom),
      right: math.max(left, right),
      bottom: math.max(top, bottom),
    );
  }

  List<List<double>> toWorldPolygon(MapPayload map) {
    final normalizedRect = normalized();
    final topLeft = _toWorldPoint(map, normalizedRect.left, normalizedRect.top);
    final topRight = _toWorldPoint(map, normalizedRect.right, normalizedRect.top);
    final bottomRight = _toWorldPoint(
      map,
      normalizedRect.right,
      normalizedRect.bottom,
    );
    final bottomLeft = _toWorldPoint(map, normalizedRect.left, normalizedRect.bottom);
    return [topLeft, topRight, bottomRight, bottomLeft];
  }

  List<double> _toWorldPoint(MapPayload map, double dx, double dy) {
    final mapX = (dx * map.width).clamp(0, map.width - 1).toInt();
    final mapYFromTop = (dy * map.height).clamp(0, map.height - 1).toInt();
    final mapY = map.height - 1 - mapYFromTop;
    final worldX = map.originX + (mapX + 0.5) * map.resolution;
    final worldY = map.originY + (mapY + 0.5) * map.resolution;
    return [worldX, worldY];
  }
}
