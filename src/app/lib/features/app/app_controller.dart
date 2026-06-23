import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/models/exploration_models.dart';
import '../../core/models/map_models.dart';
import '../../core/models/robot_models.dart';
import '../../core/network/robot_api_client.dart';

class AppController extends ChangeNotifier {
  static const _themeModePreferenceKey = 'theme_mode';

  String host = robotIp;
  int apiPort = robotPort;
  ThemeMode themeMode = ThemeMode.light;

  bool isConnected = false;
  bool isBusy = false;
  String? errorMessage;
  String? lastMessage;

  RobotStatus robotStatus = RobotStatus.offline;
  ExplorationStatus explorationStatus = ExplorationStatus.empty;
  List<SweePiMapMetadata> savedMaps = const [];
  SweePiMapMetadata? selectedMapMetadata;
  SweePiMapData? selectedMapData;
  List<MapSection> selectedSections = const [];
  String? lastSavedMapId;
  RectSelection? pendingSelection;

  RobotApiClient? _client;

  bool get isDarkMode => themeMode == ThemeMode.dark;

  Future<void> loadThemeMode() async {
    try {
      final preferences = await SharedPreferences.getInstance();
      final savedThemeMode = preferences.getString(_themeModePreferenceKey);
      themeMode = savedThemeMode == ThemeMode.dark.name
          ? ThemeMode.dark
          : ThemeMode.light;
    } catch (error) {
      debugPrint('[AppController] Failed to load theme mode: $error');
      themeMode = ThemeMode.light;
    }
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    if (themeMode == mode) {
      return;
    }
    themeMode = mode;
    notifyListeners();

    try {
      final preferences = await SharedPreferences.getInstance();
      await preferences.setString(_themeModePreferenceKey, mode.name);
    } catch (error) {
      debugPrint('[AppController] Failed to save theme mode: $error');
    }
  }

  bool get isExploring {
    final explorationState = explorationStatus.state.toLowerCase();
    final robotState = robotStatus.state.toLowerCase();
    return explorationState == 'exploring' || robotState == 'exploring';
  }

  bool get isCleaningRunning {
    final robotState = robotStatus.state.toLowerCase();
    final navState = robotStatus.nav.executionStatus.toUpperCase();
    return robotState == 'cleaning' || navState == 'CLEANING';
  }

  bool get isCleaningPaused {
    final robotState = robotStatus.state.toLowerCase();
    final navState = robotStatus.nav.executionStatus.toUpperCase();
    return robotState == 'paused' || navState == 'PAUSED';
  }

  bool get isCleaningActive => isCleaningRunning || isCleaningPaused;

  Future<void> connect() async {
    await disconnect(notify: false);
    isBusy = true;
    errorMessage = null;
    lastMessage = null;
    notifyListeners();

    try {
      _client = RobotApiClient(host: host, apiPort: apiPort);
      await _refreshRobotStatusOnly();
      explorationStatus = await _requireClient().fetchExplorationStatus();
      await _refreshMapsOnly();
      if (savedMaps.isNotEmpty && selectedMapMetadata == null) {
        await _selectMapOnly(savedMaps.first.mapId);
      }
      isConnected = true;
      lastMessage = 'Connected to http://$host:$apiPort';
    } catch (error) {
      errorMessage = '$error';
      isConnected = false;
      robotStatus = RobotStatus.offline;
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> disconnect({bool notify = true}) async {
    await _client?.close();
    _client = null;
    isConnected = false;
    if (notify) {
      notifyListeners();
    }
  }

  Future<void> refreshRobotStatus() async {
    await _runBusy(() async {
      final client = _requireClient();
      robotStatus = await client.fetchRobotStatus();
    });
  }

  Future<bool> startExploration(String mapName, String mode) async {
    var accepted = false;
    await _runBusy(() async {
      final client = _requireClient();
      final response = await client.startExploration(
        mapName: mapName.trim().isEmpty ? 'new_mock_map' : mapName.trim(),
        mode: mode,
      );
      accepted = response.accepted;
      lastMessage = response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      explorationStatus = ExplorationStatus(
        state: response.state,
        mode: response.mode,
        mapName: response.mapName,
        mapAvailable: false,
        message: response.message,
      );
      await _refreshRobotStatusOnly();
    });
    return accepted;
  }

  Future<void> refreshExplorationStatus() async {
    await _runBusy(() async {
      await _refreshRobotStatusOnly();
      explorationStatus = await _requireClient().fetchExplorationStatus();
    });
  }

  Future<bool> stopExploration() async {
    var accepted = false;
    await _runBusy(() async {
      final client = _requireClient();
      final response = await client.stopExploration();
      accepted = response.accepted;
      lastMessage = response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      lastSavedMapId = response.mapId;
      await _refreshRobotStatusOnly();
      await _refreshMapsOnly();
      if (response.mapId != null) {
        await _selectMapOnly(response.mapId!);
      }
      explorationStatus = await client.fetchExplorationStatus();
    });
    return accepted;
  }

  Future<void> sendManualDrive(String command, double speed) async {
    try {
      final response = await _requireClient().sendManualDrive(
        command: command,
        speed: speed,
      );
      lastMessage = response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        notifyListeners();
      }
    } catch (error) {
      errorMessage = '$error';
      notifyListeners();
    }
  }

  Future<void> refreshMaps() async {
    await _runBusy(_refreshMapsOnly);
  }

  Future<void> selectMap(String mapId) async {
    await _runBusy(() => _selectMapOnly(mapId));
  }

  Future<void> addSectionFromPolygon(
    String sectionName,
    List<List<double>> polygon,
  ) async {
    final metadata = selectedMapMetadata;
    if (metadata == null) {
      errorMessage = 'Select a map before adding sections.';
      notifyListeners();
      return;
    }

    final nextNumber = metadata.sections.length + 1;
    final section = MapSection(
      sectionId: 'sec_${DateTime.now().millisecondsSinceEpoch}',
      name: sectionName.trim().isEmpty ? 'Section $nextNumber' : sectionName,
      polygon: polygon,
    );
    selectedMapMetadata = metadata.copyWith(
      sections: [...metadata.sections, section],
    );
    selectedSections = [...selectedSections, section];
    lastMessage = 'Section "${section.name}" added locally.';
    notifyListeners();
  }

  Future<bool> saveSelectedMapMetadata() async {
    var saved = false;
    await _runBusy(() async {
      final metadata = selectedMapMetadata;
      if (metadata == null) {
        throw const ApiException('Select a map before saving metadata.');
      }
      debugPrint('[AppController] Saving metadata for ${metadata.mapId}');
      selectedMapMetadata = await _requireClient().updateMapMetadata(
        mapId: metadata.mapId,
        name: metadata.name,
        sections: metadata.sections,
      );
      pendingSelection = null;
      await _refreshMapsOnly();
      lastMessage = 'Map metadata saved.';
      saved = true;
      debugPrint('[AppController] Metadata saved for ${metadata.mapId}');
    });
    return saved;
  }

  void toggleSectionForCleaning(MapSection section) {
    final exists = selectedSections.any(
      (item) => item.sectionId == section.sectionId,
    );
    selectedSections = exists
        ? selectedSections
              .where((item) => item.sectionId != section.sectionId)
              .toList()
        : [...selectedSections, section];
    notifyListeners();
  }

  void selectSectionForCleaning(MapSection? section) {
    selectedSections = section == null ? const [] : [section];
    notifyListeners();
  }

  Future<bool> startCleaning({required bool fullMap}) async {
    var accepted = false;
    await _runBusy(() async {
      final metadata = selectedMapMetadata;
      if (metadata == null) {
        throw const ApiException('Select a map before starting cleaning.');
      }
      if (!fullMap && selectedSections.isEmpty) {
        errorMessage = 'Select a section before starting section cleaning.';
        return;
      }
      final sectionsToClean = fullMap
          ? const <MapSection>[]
          : [selectedSections.first];
      final response = await _requireClient().startCleaning(
        mapId: metadata.mapId,
        sections: sectionsToClean,
      );
      accepted = response.accepted;
      lastMessage = response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      await _refreshRobotStatusOnly();
    });
    return accepted;
  }

  Future<bool> pauseCleaning() async {
    var accepted = false;
    await _runBusy(() async {
      final response = await _requireClient().pauseCleaning();
      accepted = response.accepted;
      lastMessage = response.message.isEmpty
          ? 'Cleaning paused.'
          : response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      await _refreshRobotStatusOnly();
    });
    return accepted;
  }

  Future<bool> resumeCleaning() async {
    var accepted = false;
    await _runBusy(() async {
      final response = await _requireClient().resumeCleaning();
      accepted = response.accepted;
      lastMessage = response.message.isEmpty
          ? 'Cleaning resumed.'
          : response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      await _refreshRobotStatusOnly();
    });
    return accepted;
  }

  Future<bool> stopCleaning() async {
    var accepted = false;
    await _runBusy(() async {
      final response = await _requireClient().stopCleaning();
      accepted = response.accepted;
      lastMessage = response.message.isEmpty
          ? 'Cleaning stopped.'
          : response.message;
      if (!response.accepted) {
        errorMessage = response.message;
        return;
      }
      await _refreshRobotStatusOnly();
    });
    return accepted;
  }

  void updateConnectionSettings({required String host, required int apiPort}) {
    this.host = host;
    this.apiPort = apiPort;
    notifyListeners();
  }

  void updateHost(String value) {
    host = value.trim();
    notifyListeners();
  }

  void updateApiPort(String value) {
    apiPort = int.tryParse(value) ?? apiPort;
    notifyListeners();
  }

  void setPendingSelection(RectSelection? selection) {
    pendingSelection = selection;
    notifyListeners();
  }

  RobotApiClient _requireClient() {
    final client = _client;
    if (client == null) {
      throw const ApiException('Connect to the mock API server first.');
    }
    return client;
  }

  Future<void> _runBusy(Future<void> Function() action) async {
    if (isBusy) {
      return;
    }
    isBusy = true;
    errorMessage = null;
    notifyListeners();
    try {
      await action();
    } catch (error) {
      errorMessage = '$error';
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> _refreshRobotStatusOnly() async {
    robotStatus = await _requireClient().fetchRobotStatus();
  }

  Future<void> _refreshMapsOnly() async {
    savedMaps = await _requireClient().fetchMaps();
    if (selectedMapMetadata != null) {
      final selectedId = selectedMapMetadata!.mapId;
      final matching = savedMaps.where((item) => item.mapId == selectedId);
      if (matching.isNotEmpty) {
        selectedMapMetadata = matching.first;
      }
    }
  }

  Future<void> _selectMapOnly(String mapId) async {
    final client = _requireClient();
    selectedMapData = await client.fetchMap(mapId);
    selectedMapMetadata = await client.fetchMapMetadata(mapId);
    selectedSections = selectedMapMetadata!.sections
        .where(
          (section) => selectedSections.any(
            (selected) => selected.sectionId == section.sectionId,
          ),
        )
        .toList();
    pendingSelection = null;
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

  List<List<double>> toWorldPolygon(SweePiMapData map) {
    final normalizedRect = normalized();
    final topLeft = _toWorldPoint(map, normalizedRect.left, normalizedRect.top);
    final topRight = _toWorldPoint(
      map,
      normalizedRect.right,
      normalizedRect.top,
    );
    final bottomRight = _toWorldPoint(
      map,
      normalizedRect.right,
      normalizedRect.bottom,
    );
    final bottomLeft = _toWorldPoint(
      map,
      normalizedRect.left,
      normalizedRect.bottom,
    );
    return [topLeft, topRight, bottomRight, bottomLeft];
  }

  List<double> _toWorldPoint(SweePiMapData map, double dx, double dy) {
    final mapX = (dx * map.width).clamp(0, map.width - 1).toInt();
    final mapYFromTop = (dy * map.height).clamp(0, map.height - 1).toInt();
    final mapY = map.height - 1 - mapYFromTop;
    final worldX = map.originX + (mapX + 0.5) * map.resolution;
    final worldY = map.originY + (mapY + 0.5) * map.resolution;
    return [worldX, worldY];
  }
}
