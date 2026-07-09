import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../connection/robot_channel.dart';
import '../connection/robot_discovered_device.dart';
import 'ble_uuid_constants.dart';
import 'provisioning_status_model.dart';
import 'wifi_network_model.dart';

abstract class BleWifiProvisioningService {
  Stream<ProvisioningStatus> get statusStream;
  bool get isConnected;
  bool get isProvisioningServiceDiscovered;
  bool get hasWifiConfigCharacteristic;

  Future<RobotDiscoveredDevice> connect(RobotDiscoveredDevice robot);
  Future<RobotDiscoveredDevice> readRobotInfo();
  Future<List<WifiNetwork>> scanWifiNetworks();
  Future<void> sendWifiCredentials({
    required String ssid,
    required String password,
    String country = 'LK',
  });
  Future<ProvisioningStatus> readWifiStatus();
  Future<void> disconnect();
}

class FlutterBlueBleWifiProvisioningService
    implements BleWifiProvisioningService {
  FlutterBlueBleWifiProvisioningService();

  final _statusController = StreamController<ProvisioningStatus>.broadcast();
  BluetoothDevice? _device;
  RobotDiscoveredDevice? _robot;
  final _characteristics = <String, BluetoothCharacteristic>{};
  bool _provisioningServiceDiscovered = false;
  String _lastDiscoveryReport = 'BLE service discovery has not run yet.';

  @override
  Stream<ProvisioningStatus> get statusStream => _statusController.stream;

  @override
  bool get isConnected => _device != null;

  @override
  bool get isProvisioningServiceDiscovered => _provisioningServiceDiscovered;

  @override
  bool get hasWifiConfigCharacteristic =>
      _characteristics.containsKey(WIFI_CONFIG_CHARACTERISTIC_UUID);

  @override
  Future<RobotDiscoveredDevice> connect(RobotDiscoveredDevice robot) async {
    final remoteId = robot.bleDeviceId;
    if (remoteId == null || remoteId.isEmpty) {
      throw StateError(
        'No Bluetooth device ID is available for ${robot.name}.',
      );
    }

    await disconnect();
    final device = BluetoothDevice.fromId(remoteId);
    await device.connect(
      license: License.nonprofit,
      timeout: const Duration(seconds: 20),
    );
    _device = device;
    _robot = robot;
    await _discoverCharacteristics(device);
    final info = await readRobotInfo();
    _statusController.add(
      const ProvisioningStatus(
        state: WifiProvisioningState.idle,
        message: 'Connected over Bluetooth.',
      ),
    );
    return info;
  }

  @override
  Future<RobotDiscoveredDevice> readRobotInfo() async {
    final characteristic = _characteristics[ROBOT_INFO_CHARACTERISTIC_UUID];
    if (characteristic == null) {
      final robot = _robot;
      if (robot == null) {
        throw StateError('Connect to a SweePi over Bluetooth first.');
      }
      return robot;
    }

    final json = await _readJson(characteristic);
    final robotId = json['robot_id'] as String? ?? _robot?.robotId ?? 'sweepi';
    final name = json['name'] as String? ?? _robot?.name ?? robotId;
    final updated =
        (_robot ??
                RobotDiscoveredDevice(
                  robotId: robotId,
                  name: name,
                  channel: RobotChannel.bluetooth,
                ))
            .copyWith(
              robotId: robotId,
              name: name,
              status: json['status'] as String?,
              model: json['model'] as String?,
            );
    _robot = updated;
    return updated;
  }

  @override
  Future<List<WifiNetwork>> scanWifiNetworks() async {
    _statusController.add(
      const ProvisioningStatus(
        state: WifiProvisioningState.scanning,
        message: 'Scanning for Wi-Fi networks...',
      ),
    );
    final command = _characteristics[SETUP_COMMAND_CHARACTERISTIC_UUID];
    if (command != null) {
      await _writeJson(command, const {'command': 'scan_wifi'});
    }
    final scan = _characteristics[WIFI_SCAN_CHARACTERISTIC_UUID];
    if (scan == null) {
      return const [];
    }
    final payload = await _readJson(scan);
    final rawNetworks = payload['networks'] is List
        ? payload['networks'] as List
        : const [];
    return rawNetworks
        .whereType<Map>()
        .map((item) => WifiNetwork.fromJson(item.cast<String, dynamic>()))
        .where((network) => network.ssid.isNotEmpty)
        .toList();
  }

  @override
  Future<void> sendWifiCredentials({
    required String ssid,
    required String password,
    String country = 'LK',
  }) async {
    final config = _characteristics[WIFI_CONFIG_CHARACTERISTIC_UUID];
    if (config == null) {
      _logDiscoveryFailure(
        'Wi-Fi config characteristic is not available before credential write.',
      );
      throw const ProvisioningException(
        'Wi-Fi setup is not ready. Reconnect to SweePi and try again.',
      );
    }
    _statusController.add(
      ProvisioningStatus(
        state: WifiProvisioningState.connecting,
        ssid: ssid,
        message: 'Connecting to your Wi-Fi...',
      ),
    );
    await _writeJson(config, {
      'ssid': ssid,
      'password': password,
      'country': country,
    });
  }

  @override
  Future<ProvisioningStatus> readWifiStatus() async {
    final status = _characteristics[WIFI_STATUS_CHARACTERISTIC_UUID];
    if (status == null) {
      return const ProvisioningStatus(
        state: WifiProvisioningState.failedUnknown,
        message: 'Wi-Fi status characteristic was not found.',
      );
    }
    final parsed = ProvisioningStatus.fromJson(await _readJson(status));
    _statusController.add(parsed);
    return parsed;
  }

  @override
  Future<void> disconnect() async {
    final device = _device;
    _device = null;
    _robot = null;
    _provisioningServiceDiscovered = false;
    _characteristics.clear();
    if (device != null) {
      await device.disconnect();
    }
  }

  Future<void> _discoverCharacteristics(BluetoothDevice device) async {
    _characteristics.clear();
    _provisioningServiceDiscovered = false;
    final services = await device.discoverServices();
    _provisioningServiceDiscovered = services.any(
      (service) => uuidEquals(
        service.uuid.str128,
        SweePiBleUuids.sweepiProvisioningServiceUuid,
      ),
    );

    final discovered = findSweePiProvisioningCharacteristics(
      services: services,
      requiredCharacteristicUuids: SweePiBleUuids.requiredCharacteristicUuids,
      serviceUuidOf: (service) => service.uuid.str128,
      characteristicsOf: (service) => service.characteristics,
      characteristicUuidOf: (characteristic) => characteristic.uuid.str128,
    );
    _characteristics.addAll(discovered);
    _lastDiscoveryReport = _formatDiscoveryReport(device, services);

    final missing = SweePiBleUuids.requiredCharacteristicUuids
        .where((uuid) => !_characteristics.containsKey(uuid))
        .toList();
    if (!_provisioningServiceDiscovered || missing.isNotEmpty) {
      _logDiscoveryFailure(
        _provisioningServiceDiscovered
            ? 'Missing required BLE characteristics: ${missing.join(', ')}.'
            : 'SweePi provisioning service was not discovered.',
      );
    }
  }

  String _formatDiscoveryReport(
    BluetoothDevice device,
    List<BluetoothService> services,
  ) {
    final buffer = StringBuffer()
      ..writeln('Device id: ${device.remoteId.str}')
      ..writeln('Device name: ${_robot?.name ?? 'unknown'}')
      ..writeln('Platform name: ${device.platformName}')
      ..writeln(
        'Expected service UUID: ${SweePiBleUuids.sweepiProvisioningServiceUuid}',
      )
      ..writeln('Expected WIFI_CONFIG UUID: $WIFI_CONFIG_CHARACTERISTIC_UUID')
      ..writeln('Discovered services and characteristics:');

    for (final service in services) {
      buffer.writeln('- ${normalizeUuid(service.uuid.str128)}');
      for (final characteristic in service.characteristics) {
        buffer.writeln('  - ${normalizeUuid(characteristic.uuid.str128)}');
      }
    }

    buffer.writeln('Required characteristic discovery:');
    for (final uuid in SweePiBleUuids.requiredCharacteristicUuids) {
      buffer.writeln('- $uuid: ${_characteristics.containsKey(uuid)}');
    }
    return buffer.toString();
  }

  void _logDiscoveryFailure(String reason) {
    debugPrint('[BLE Provisioning] $reason\n$_lastDiscoveryReport');
  }

  Future<Map<String, dynamic>> _readJson(
    BluetoothCharacteristic characteristic,
  ) async {
    final raw = await characteristic.read();
    final decoded = jsonDecode(utf8.decode(raw));
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    if (decoded is List) {
      return {'networks': decoded};
    }
    return const {};
  }

  Future<void> _writeJson(
    BluetoothCharacteristic characteristic,
    Map<String, dynamic> payload,
  ) async {
    await characteristic.write(utf8.encode(jsonEncode(payload)));
  }
}

class ProvisioningException implements Exception {
  const ProvisioningException(this.message);

  final String message;

  @override
  String toString() => message;
}

@visibleForTesting
Map<String, TCharacteristic>
findSweePiProvisioningCharacteristics<TService, TCharacteristic>({
  required Iterable<TService> services,
  required Iterable<String> requiredCharacteristicUuids,
  required String Function(TService service) serviceUuidOf,
  required Iterable<TCharacteristic> Function(TService service)
  characteristicsOf,
  required String Function(TCharacteristic characteristic) characteristicUuidOf,
  String provisioningServiceUuid = SWEEPI_PROVISIONING_SERVICE_UUID,
}) {
  final requiredUuids = {
    for (final uuid in requiredCharacteristicUuids) normalizeUuid(uuid),
  };
  final found = <String, TCharacteristic>{};

  for (final service in services) {
    if (!uuidEquals(serviceUuidOf(service), provisioningServiceUuid)) {
      continue;
    }
    for (final characteristic in characteristicsOf(service)) {
      final uuid = normalizeUuid(characteristicUuidOf(characteristic));
      if (requiredUuids.contains(uuid)) {
        found[uuid] = characteristic;
      }
    }
  }

  return found;
}

class MockBleWifiProvisioningService implements BleWifiProvisioningService {
  MockBleWifiProvisioningService({this.shouldConnectToWifi = true});

  final bool shouldConnectToWifi;
  final _statusController = StreamController<ProvisioningStatus>.broadcast();
  RobotDiscoveredDevice? _robot;
  ProvisioningStatus _lastStatus = const ProvisioningStatus(
    state: WifiProvisioningState.idle,
  );

  @override
  Stream<ProvisioningStatus> get statusStream => _statusController.stream;

  @override
  bool get isConnected => _robot != null;

  @override
  bool get isProvisioningServiceDiscovered => _robot != null;

  @override
  bool get hasWifiConfigCharacteristic => _robot != null;

  @override
  Future<RobotDiscoveredDevice> connect(RobotDiscoveredDevice robot) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    _robot = robot.copyWith(
      status: 'setup mode',
      model: robot.model ?? 'sweepi',
    );
    _statusController.add(
      const ProvisioningStatus(
        state: WifiProvisioningState.idle,
        message: 'Connected over Bluetooth.',
      ),
    );
    return _robot!;
  }

  @override
  Future<RobotDiscoveredDevice> readRobotInfo() async {
    final robot = _robot;
    if (robot == null) {
      throw StateError('Connect to a SweePi over Bluetooth first.');
    }
    return robot;
  }

  @override
  Future<List<WifiNetwork>> scanWifiNetworks() async {
    _statusController.add(
      const ProvisioningStatus(state: WifiProvisioningState.scanning),
    );
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return const [
      WifiNetwork(ssid: 'Home WiFi', rssi: -42, security: 'wpa2'),
      WifiNetwork(ssid: 'SweePi Lab', rssi: -55, security: 'wpa2'),
      WifiNetwork(ssid: 'Guest Network', rssi: -68, security: 'wpa2'),
    ];
  }

  @override
  Future<void> sendWifiCredentials({
    required String ssid,
    required String password,
    String country = 'LK',
  }) async {
    _lastStatus = ProvisioningStatus(
      state: WifiProvisioningState.connecting,
      ssid: ssid,
      message: 'Connecting to your Wi-Fi...',
    );
    _statusController.add(_lastStatus);
    await Future<void>.delayed(const Duration(milliseconds: 600));
    _lastStatus = shouldConnectToWifi
        ? ProvisioningStatus(
            state: WifiProvisioningState.connected,
            ssid: ssid,
            ip: '192.168.1.45',
            hostname: 'sweepi-8f23.local',
            robotId: _robot?.robotId ?? 'sweepi-8f23',
            message: 'Connected to Wi-Fi.',
          )
        : ProvisioningStatus(
            state: WifiProvisioningState.failedAuth,
            ssid: ssid,
            message: 'Wi-Fi password was rejected.',
          );
    _statusController.add(_lastStatus);
  }

  @override
  Future<ProvisioningStatus> readWifiStatus() async => _lastStatus;

  @override
  Future<void> disconnect() async {
    _robot = null;
  }
}
