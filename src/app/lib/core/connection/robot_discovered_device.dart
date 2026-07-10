import 'robot_channel.dart';

class RobotDiscoveredDevice {
  RobotDiscoveredDevice({
    required this.robotId,
    required this.name,
    required this.channel,
    this.hostName,
    this.ipAddress,
    this.apiPort = 8080,
    this.websocketPort = 8765,
    this.serviceName,
    this.model,
    this.bleDeviceId,
    this.rssi,
    this.status,
    this.txtRecords = const {},
    this.lastKnownWifiSsid,
    this.lastSuccessfulConnection,
    DateTime? lastSeen,
  }) : lastSeen = lastSeen ?? DateTime.now();

  final String robotId;
  final String name;
  final RobotChannel channel;
  final String? hostName;
  final String? ipAddress;
  final int apiPort;
  final int websocketPort;
  final String? serviceName;
  final String? model;
  final String? bleDeviceId;
  final int? rssi;
  final String? status;
  final Map<String, String> txtRecords;
  final String? lastKnownWifiSsid;
  final DateTime? lastSuccessfulConnection;
  final DateTime lastSeen;

  bool get hasWifi =>
      channel == RobotChannel.wifi || channel == RobotChannel.both;
  bool get hasBluetooth =>
      channel == RobotChannel.bluetooth || channel == RobotChannel.both;
  String? get bestHost => ipAddress?.isNotEmpty == true ? ipAddress : hostName;
  Uri? get apiBaseUri {
    final host = bestHost;
    if (host == null || host.isEmpty) {
      return null;
    }
    return Uri(scheme: 'http', host: host, port: apiPort);
  }

  RobotDiscoveredDevice copyWith({
    String? robotId,
    String? name,
    RobotChannel? channel,
    String? hostName,
    String? ipAddress,
    int? apiPort,
    int? websocketPort,
    String? serviceName,
    String? model,
    String? bleDeviceId,
    int? rssi,
    String? status,
    Map<String, String>? txtRecords,
    String? lastKnownWifiSsid,
    DateTime? lastSuccessfulConnection,
    DateTime? lastSeen,
  }) {
    return RobotDiscoveredDevice(
      robotId: robotId ?? this.robotId,
      name: name ?? this.name,
      channel: channel ?? this.channel,
      hostName: hostName ?? this.hostName,
      ipAddress: ipAddress ?? this.ipAddress,
      apiPort: apiPort ?? this.apiPort,
      websocketPort: websocketPort ?? this.websocketPort,
      serviceName: serviceName ?? this.serviceName,
      model: model ?? this.model,
      bleDeviceId: bleDeviceId ?? this.bleDeviceId,
      rssi: rssi ?? this.rssi,
      status: status ?? this.status,
      txtRecords: txtRecords ?? this.txtRecords,
      lastKnownWifiSsid: lastKnownWifiSsid ?? this.lastKnownWifiSsid,
      lastSuccessfulConnection:
          lastSuccessfulConnection ?? this.lastSuccessfulConnection,
      lastSeen: lastSeen ?? this.lastSeen,
    );
  }

  RobotDiscoveredDevice merge(RobotDiscoveredDevice other) {
    final mergedChannel =
        hasWifi && other.hasBluetooth ||
            hasBluetooth && other.hasWifi ||
            other.channel == RobotChannel.both ||
            channel == RobotChannel.both
        ? RobotChannel.both
        : other.channel;
    return copyWith(
      channel: mergedChannel,
      hostName: other.hostName ?? hostName,
      ipAddress: other.ipAddress ?? ipAddress,
      apiPort: other.apiPort,
      websocketPort: other.websocketPort,
      serviceName: other.serviceName ?? serviceName,
      model: other.model ?? model,
      bleDeviceId: other.bleDeviceId ?? bleDeviceId,
      rssi: other.rssi ?? rssi,
      status: other.status ?? status,
      txtRecords: {...txtRecords, ...other.txtRecords},
      lastKnownWifiSsid: other.lastKnownWifiSsid ?? lastKnownWifiSsid,
      lastSuccessfulConnection:
          other.lastSuccessfulConnection ?? lastSuccessfulConnection,
      lastSeen: other.lastSeen,
    );
  }

  Map<String, Object?> toPersistenceJson() {
    return {
      'robot_id': robotId,
      'name': name,
      'last_known_api_host': bestHost,
      'last_known_hostname': hostName,
      'last_known_mdns_service_name': serviceName,
      'last_known_ip_debug': ipAddress,
      'model': model,
      'api_port': apiPort,
      'websocket_port': websocketPort,
      'ble_device_id': bleDeviceId,
      'last_known_wifi_ssid': lastKnownWifiSsid,
      'last_successful_connection_at': lastSuccessfulConnection
          ?.toIso8601String(),
    };
  }

  factory RobotDiscoveredDevice.fromPersistenceJson(Map<String, dynamic> json) {
    final lastKnownApiHost = json['last_known_api_host'] as String?;
    final lastSuccessfulConnectionText =
        json['last_successful_connection_at'] as String?;
    return RobotDiscoveredDevice(
      robotId: json['robot_id'] as String? ?? 'unknown',
      name: json['name'] as String? ?? 'SweePi',
      channel: RobotChannel.none,
      hostName: json['last_known_hostname'] as String? ?? lastKnownApiHost,
      ipAddress: json['last_known_ip_debug'] as String?,
      serviceName: json['last_known_mdns_service_name'] as String?,
      model: json['model'] as String?,
      apiPort: json['api_port'] as int? ?? 8080,
      websocketPort: json['websocket_port'] as int? ?? 8765,
      bleDeviceId: json['ble_device_id'] as String?,
      lastKnownWifiSsid: json['last_known_wifi_ssid'] as String?,
      lastSuccessfulConnection: lastSuccessfulConnectionText == null
          ? null
          : DateTime.tryParse(lastSuccessfulConnectionText),
    );
  }
}
