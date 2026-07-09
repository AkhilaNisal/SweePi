import 'robot_channel.dart';
import 'robot_discovered_device.dart';

enum RobotConnectionStatus {
  noRobotFound,
  scanning,
  bleFound,
  wifiFound,
  bothFound,
  bleConnected,
  wifiConnected,
  provisioning,
  wifiConnecting,
  connected,
  discoveryFailed,
  error,
}

class RobotConnectionState {
  const RobotConnectionState({
    required this.status,
    required this.channel,
    this.discoveredRobots = const [],
    this.selectedRobot,
    this.savedRobot,
    this.message,
    this.error,
    this.debugMdnsServices = const [],
    this.debugBleDevices = const [],
  });

  factory RobotConnectionState.initial() {
    return const RobotConnectionState(
      status: RobotConnectionStatus.noRobotFound,
      channel: RobotChannel.none,
      message: 'Searching for SweePi...',
    );
  }

  final RobotConnectionStatus status;
  final RobotChannel channel;
  final List<RobotDiscoveredDevice> discoveredRobots;
  final RobotDiscoveredDevice? selectedRobot;
  final RobotDiscoveredDevice? savedRobot;
  final String? message;
  final String? error;
  final List<String> debugMdnsServices;
  final List<String> debugBleDevices;

  bool get isScanning => status == RobotConnectionStatus.scanning;
  bool get hasWifiRobot => discoveredRobots.any((robot) => robot.hasWifi);
  bool get hasBluetoothRobot =>
      discoveredRobots.any((robot) => robot.hasBluetooth);

  RobotConnectionState copyWith({
    RobotConnectionStatus? status,
    RobotChannel? channel,
    List<RobotDiscoveredDevice>? discoveredRobots,
    RobotDiscoveredDevice? selectedRobot,
    RobotDiscoveredDevice? savedRobot,
    String? message,
    String? error,
    List<String>? debugMdnsServices,
    List<String>? debugBleDevices,
    bool clearError = false,
  }) {
    return RobotConnectionState(
      status: status ?? this.status,
      channel: channel ?? this.channel,
      discoveredRobots: discoveredRobots ?? this.discoveredRobots,
      selectedRobot: selectedRobot ?? this.selectedRobot,
      savedRobot: savedRobot ?? this.savedRobot,
      message: message ?? this.message,
      error: clearError ? null : error ?? this.error,
      debugMdnsServices: debugMdnsServices ?? this.debugMdnsServices,
      debugBleDevices: debugBleDevices ?? this.debugBleDevices,
    );
  }
}
