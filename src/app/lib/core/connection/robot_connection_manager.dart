import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../discovery/ble_robot_discovery_service.dart';
import '../discovery/mdns_robot_discovery_service.dart';
import 'robot_channel.dart';
import 'robot_connection_state.dart';
import 'robot_discovered_device.dart';

class RobotConnectionManager extends ChangeNotifier {
  RobotConnectionManager({
    RobotMdnsDiscoveryService? mdnsDiscoveryService,
    BleRobotDiscoveryService? bleDiscoveryService,
    SharedPreferences? preferences,
  }) : _mdnsDiscoveryService =
           mdnsDiscoveryService ?? const MulticastMdnsRobotDiscoveryService(),
       _bleDiscoveryService =
           bleDiscoveryService ?? const FlutterBlueBleRobotDiscoveryService(),
       _preferences = preferences;

  static const _selectedRobotPreferenceKey = 'selected_robot_identity';

  final RobotMdnsDiscoveryService _mdnsDiscoveryService;
  final BleRobotDiscoveryService _bleDiscoveryService;
  SharedPreferences? _preferences;

  RobotConnectionState state = RobotConnectionState.initial();

  Future<void> loadSavedRobot() async {
    final preferences = await _getPreferences();
    final saved = preferences.getString(_selectedRobotPreferenceKey);
    if (saved == null || saved.isEmpty) {
      return;
    }
    try {
      final decoded = jsonDecode(saved) as Map<String, dynamic>;
      state = state.copyWith(
        savedRobot: RobotDiscoveredDevice.fromPersistenceJson(decoded),
      );
      notifyListeners();
    } catch (error) {
      debugPrint('[ConnectionManager] Failed to load saved robot: $error');
    }
  }

  void markAutoConnecting({String message = 'Looking for SweePi...'}) {
    state = state.copyWith(
      status: RobotConnectionStatus.autoConnecting,
      channel: RobotChannel.none,
      message: message,
      clearError: true,
    );
    notifyListeners();
  }

  Future<List<RobotDiscoveredDevice>> discoverRobots({
    Duration mdnsTimeout = const Duration(seconds: 4),
    Duration bleTimeout = const Duration(seconds: 5),
  }) async {
    state = state.copyWith(
      status: RobotConnectionStatus.scanning,
      channel: RobotChannel.none,
      message: 'Searching for SweePi...',
      clearError: true,
    );
    notifyListeners();

    try {
      final results = await Future.wait([
        _mdnsDiscoveryService.discover(timeout: mdnsTimeout),
        _bleDiscoveryService.scan(timeout: bleTimeout),
      ]);
      final wifiRobots = results[0];
      final bleRobots = results[1];
      final robots = _mergeRobots([...wifiRobots, ...bleRobots]);
      final selected = _selectPreferredRobot(robots);
      final summary = _summarize(robots);

      state = state.copyWith(
        status: summary.status,
        channel: summary.channel,
        discoveredRobots: robots,
        selectedRobot: selected,
        message: summary.message,
        debugMdnsServices: wifiRobots
            .map((robot) => robot.serviceName ?? robot.name)
            .toList(),
        debugBleDevices: bleRobots
            .map((robot) => robot.bleDeviceId ?? robot.name)
            .toList(),
        clearError: true,
      );
      notifyListeners();
      return robots;
    } catch (error) {
      state = state.copyWith(
        status: RobotConnectionStatus.discoveryFailed,
        channel: RobotChannel.none,
        message:
            'Could not find SweePi on this Wi-Fi. Make sure your phone and robot are on the same network.',
        error: '$error',
      );
      notifyListeners();
      return const [];
    }
  }

  Future<void> selectRobot(RobotDiscoveredDevice robot) async {
    state = state.copyWith(
      selectedRobot: robot,
      channel: robot.channel,
      status: robot.hasWifi
          ? RobotConnectionStatus.wifiFound
          : RobotConnectionStatus.bleFound,
      message: '${robot.name} selected.',
      clearError: true,
    );
    notifyListeners();
    await _saveSelectedRobot(robot);
  }

  Future<void> markBleConnected(RobotDiscoveredDevice robot) async {
    state = state.copyWith(
      selectedRobot: robot,
      channel: robot.hasWifi ? RobotChannel.both : RobotChannel.bluetooth,
      status: RobotConnectionStatus.bleConnected,
      message: 'SweePi found nearby.',
      clearError: true,
    );
    notifyListeners();
    await _saveSelectedRobot(robot);
  }

  void markProvisioning() {
    state = state.copyWith(
      status: RobotConnectionStatus.provisioning,
      message: 'Connecting to your Wi-Fi...',
      clearError: true,
    );
    notifyListeners();
  }

  void markWifiConnecting() {
    state = state.copyWith(
      status: RobotConnectionStatus.wifiConnecting,
      message: 'Switching to Wi-Fi connection...',
      clearError: true,
    );
    notifyListeners();
  }

  Future<void> markWifiConnected(RobotDiscoveredDevice robot) async {
    state = state.copyWith(
      selectedRobot: robot,
      channel: robot.hasBluetooth ? RobotChannel.both : RobotChannel.wifi,
      status: RobotConnectionStatus.connected,
      message: 'Connected to SweePi.',
      clearError: true,
    );
    notifyListeners();
    await _saveSelectedRobot(robot);
  }

  Future<void> markApiConnected(
    RobotDiscoveredDevice robot, {
    String? lastKnownWifiSsid,
  }) async {
    final connectedRobot = robot.copyWith(
      channel: robot.hasBluetooth ? RobotChannel.both : RobotChannel.wifi,
      lastKnownWifiSsid: lastKnownWifiSsid,
      lastSuccessfulConnection: DateTime.now(),
    );
    state = state.copyWith(
      selectedRobot: connectedRobot,
      channel: connectedRobot.channel,
      status: RobotConnectionStatus.connected,
      message: 'Connected to SweePi.',
      clearError: true,
    );
    notifyListeners();
    await _saveSelectedRobot(connectedRobot);
  }

  void markTemporaryWifiConnected(RobotDiscoveredDevice robot) {
    state = state.copyWith(
      selectedRobot: robot,
      channel: robot.hasBluetooth ? RobotChannel.both : RobotChannel.wifi,
      status: RobotConnectionStatus.connected,
      message:
          'Robot connected to Wi-Fi, but automatic discovery failed. Make sure your phone is on the same Wi-Fi network.',
      clearError: true,
    );
    notifyListeners();
  }

  void markError(String message) {
    state = state.copyWith(
      status: RobotConnectionStatus.error,
      message: message,
      error: message,
    );
    notifyListeners();
  }

  Future<void> clearSelectedRobot() async {
    final preferences = await _getPreferences();
    await preferences.remove(_selectedRobotPreferenceKey);
    state = RobotConnectionState.initial();
    notifyListeners();
  }

  List<RobotDiscoveredDevice> _mergeRobots(List<RobotDiscoveredDevice> robots) {
    final byKey = <String, RobotDiscoveredDevice>{};
    for (final robot in robots) {
      final key = robot.robotId.isNotEmpty ? robot.robotId : robot.name;
      final existing = byKey[key];
      byKey[key] = existing == null ? robot : existing.merge(robot);
    }
    return byKey.values.toList()..sort((a, b) {
      if (a.hasWifi != b.hasWifi) {
        return a.hasWifi ? -1 : 1;
      }
      return a.name.compareTo(b.name);
    });
  }

  RobotDiscoveredDevice? _selectPreferredRobot(
    List<RobotDiscoveredDevice> robots,
  ) {
    if (robots.isEmpty) {
      return null;
    }
    final savedId = state.savedRobot?.robotId;
    if (savedId != null) {
      final savedMatches = robots.where((robot) => robot.robotId == savedId);
      if (savedMatches.isNotEmpty) {
        final wifiSaved = savedMatches.where((robot) => robot.hasWifi);
        return wifiSaved.isNotEmpty ? wifiSaved.first : savedMatches.first;
      }
    }
    final wifiRobots = robots.where((robot) => robot.hasWifi);
    return wifiRobots.isNotEmpty ? wifiRobots.first : robots.first;
  }

  _DiscoverySummary _summarize(List<RobotDiscoveredDevice> robots) {
    if (robots.isEmpty) {
      return const _DiscoverySummary(
        status: RobotConnectionStatus.noRobotFound,
        channel: RobotChannel.none,
        message: 'Set up new SweePi.',
      );
    }
    final hasWifi = robots.any((robot) => robot.hasWifi);
    final hasBle = robots.any((robot) => robot.hasBluetooth);
    if (hasWifi && hasBle) {
      return const _DiscoverySummary(
        status: RobotConnectionStatus.bothFound,
        channel: RobotChannel.both,
        message: 'SweePi found on Wi-Fi. Bluetooth is available for setup.',
      );
    }
    if (hasWifi) {
      return const _DiscoverySummary(
        status: RobotConnectionStatus.wifiFound,
        channel: RobotChannel.wifi,
        message: 'SweePi found on Wi-Fi.',
      );
    }
    return const _DiscoverySummary(
      status: RobotConnectionStatus.bleFound,
      channel: RobotChannel.bluetooth,
      message: 'SweePi found nearby.',
    );
  }

  Future<void> _saveSelectedRobot(RobotDiscoveredDevice robot) async {
    final preferences = await _getPreferences();
    await preferences.setString(
      _selectedRobotPreferenceKey,
      jsonEncode(robot.toPersistenceJson()),
    );
    state = state.copyWith(savedRobot: robot);
  }

  Future<SharedPreferences> _getPreferences() async {
    final preferences = _preferences;
    if (preferences != null) {
      return preferences;
    }
    return _preferences = await SharedPreferences.getInstance();
  }
}

class _DiscoverySummary {
  const _DiscoverySummary({
    required this.status,
    required this.channel,
    required this.message,
  });

  final RobotConnectionStatus status;
  final RobotChannel channel;
  final String message;
}
