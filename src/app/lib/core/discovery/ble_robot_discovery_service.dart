import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

import '../connection/robot_channel.dart';
import '../connection/robot_discovered_device.dart';
import '../provisioning/ble_uuid_constants.dart';

abstract class BleRobotDiscoveryService {
  Future<List<RobotDiscoveredDevice>> scan({
    Duration timeout = const Duration(seconds: 5),
  });
}

class FlutterBlueBleRobotDiscoveryService implements BleRobotDiscoveryService {
  const FlutterBlueBleRobotDiscoveryService();

  @override
  Future<List<RobotDiscoveredDevice>> scan({
    Duration timeout = const Duration(seconds: 5),
  }) async {
    try {
      if (!await FlutterBluePlus.isSupported) {
        return const [];
      }
      await _requestPermissions();

      final serviceGuid = Guid(SweePiBleUuids.sweepiProvisioningServiceUuid);
      var results = await _scanWithServices(serviceGuid, timeout);
      if (results.isEmpty) {
        results = await _scanWithNamePrefix(timeout);
      }
      return results.map(_toRobot).whereType<RobotDiscoveredDevice>().toList();
    } catch (error) {
      debugPrint('[BLE] SweePi scan failed: $error');
      return const [];
    }
  }

  Future<void> _requestPermissions() async {
    if (kIsWeb) {
      return;
    }
    if (Platform.isAndroid) {
      await [
        Permission.bluetoothScan,
        Permission.bluetoothConnect,
        Permission.locationWhenInUse,
      ].request();
    } else if (Platform.isIOS || Platform.isMacOS) {
      await Permission.bluetooth.request();
    }
  }

  Future<List<ScanResult>> _scanWithServices(
    Guid serviceGuid,
    Duration timeout,
  ) async {
    await FlutterBluePlus.startScan(
      withServices: [serviceGuid],
      timeout: timeout,
      androidUsesFineLocation: false,
    );
    await Future<void>.delayed(timeout + const Duration(milliseconds: 250));
    if (FlutterBluePlus.isScanningNow) {
      await FlutterBluePlus.stopScan();
    }
    return FlutterBluePlus.lastScanResults
        .where((result) => _looksLikeSweePi(result, serviceGuid))
        .toList();
  }

  Future<List<ScanResult>> _scanWithNamePrefix(Duration timeout) async {
    await FlutterBluePlus.startScan(
      withKeywords: const ['SweePi'],
      timeout: timeout,
      androidUsesFineLocation: false,
    );
    await Future<void>.delayed(timeout + const Duration(milliseconds: 250));
    if (FlutterBluePlus.isScanningNow) {
      await FlutterBluePlus.stopScan();
    }
    return FlutterBluePlus.lastScanResults
        .where((result) => _looksLikeSweePi(result, null))
        .toList();
  }

  bool _looksLikeSweePi(ScanResult result, Guid? serviceGuid) {
    final name = _friendlyBleName(result);
    final serviceMatch =
        serviceGuid != null &&
        result.advertisementData.serviceUuids.contains(serviceGuid);
    return serviceMatch || name.toLowerCase().startsWith('sweepi');
  }

  RobotDiscoveredDevice? _toRobot(ScanResult result) {
    final name = _friendlyBleName(result);
    if (!name.toLowerCase().startsWith('sweepi')) {
      return null;
    }
    final normalized = name.toLowerCase();
    return RobotDiscoveredDevice(
      robotId: normalized.replaceAll(RegExp(r'[^a-z0-9-]'), '-'),
      name: name,
      channel: RobotChannel.bluetooth,
      bleDeviceId: result.device.remoteId.str,
      rssi: result.rssi,
      status: 'nearby',
    );
  }

  String _friendlyBleName(ScanResult result) {
    final advName = result.advertisementData.advName.trim();
    if (advName.isNotEmpty) {
      return advName;
    }
    final platformName = result.device.platformName.trim();
    if (platformName.isNotEmpty) {
      return platformName;
    }
    final id = result.device.remoteId.str;
    return 'SweePi-${id.substring(0, id.length < 4 ? id.length : 4)}';
  }
}

class MockBleRobotDiscoveryService implements BleRobotDiscoveryService {
  const MockBleRobotDiscoveryService({this.shouldFindRobot = true});

  final bool shouldFindRobot;

  @override
  Future<List<RobotDiscoveredDevice>> scan({
    Duration timeout = const Duration(seconds: 5),
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!shouldFindRobot) {
      return const [];
    }
    return [
      RobotDiscoveredDevice(
        robotId: 'sweepi-8f23',
        name: 'SweePi-8F23',
        channel: RobotChannel.bluetooth,
        bleDeviceId: 'mock-ble-sweepi-8f23',
        rssi: -48,
        status: 'setup available',
      ),
    ];
  }
}
