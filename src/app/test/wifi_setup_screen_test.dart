import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sweepi/core/connection/robot_channel.dart';
import 'package:sweepi/core/connection/robot_discovered_device.dart';
import 'package:sweepi/core/provisioning/ble_wifi_provisioning_service.dart';
import 'package:sweepi/core/provisioning/provisioning_status_model.dart';
import 'package:sweepi/core/provisioning/wifi_network_model.dart';
import 'package:sweepi/features/app/app_controller.dart';
import 'package:sweepi/features/setup/wifi_setup_screen.dart';

void main() {
  test('Connect button enable logic covers BLE and Wi-Fi form readiness', () {
    const secureNetwork = WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2');

    expect(
      canConnectToWifi(
        bleConnected: false,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      isFalse,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: false,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      isFalse,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: '',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      isFalse,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: '',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      isFalse,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      isTrue,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'guest',
        password: '',
        selectedNetwork: const WifiNetwork(ssid: 'guest', security: 'open'),
        isConnecting: false,
      ),
      isTrue,
    );
  });

  testWidgets('Connect button updates when password text changes', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    final controller = AppController();
    addTearDown(controller.dispose);
    addTearDown(service.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: WifiSetupScreen(
          controller: controller,
          robot: _robot(),
          networks: const [WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2')],
          provisioningService: service,
        ),
      ),
    );

    expect(_connectButton(tester).onPressed, isNull);

    await tester.enterText(find.byType(TextField).last, 'password');
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
  });

  testWidgets('Connect button updates when selected network changes', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    final controller = AppController();
    addTearDown(controller.dispose);
    addTearDown(service.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: WifiSetupScreen(
          controller: controller,
          robot: _robot(),
          networks: const [
            WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2'),
            WifiNetwork(ssid: 'guest', security: 'open'),
          ],
          provisioningService: service,
        ),
      ),
    );

    expect(_connectButton(tester).onPressed, isNull);

    await tester.tap(find.text('guest'));
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
  });
}

FilledButton _connectButton(WidgetTester tester) {
  final finder = find.ancestor(
    of: find.text('Connect SweePi'),
    matching: find.byWidgetPredicate((widget) => widget is FilledButton),
  );
  return tester.widget<FilledButton>(finder);
}

RobotDiscoveredDevice _robot() {
  return RobotDiscoveredDevice(
    robotId: 'sweepi-dev-001',
    name: 'SweePi Dev',
    channel: RobotChannel.bluetooth,
    bleDeviceId: 'mock-ble-id',
  );
}

class _FakeProvisioningService implements BleWifiProvisioningService {
  final _statusController = StreamController<ProvisioningStatus>.broadcast();

  @override
  Stream<ProvisioningStatus> get statusStream => _statusController.stream;

  @override
  bool isConnected = true;

  @override
  bool isProvisioningServiceDiscovered = true;

  @override
  bool hasWifiConfigCharacteristic = true;

  @override
  Future<RobotDiscoveredDevice> connect(RobotDiscoveredDevice robot) async {
    return robot;
  }

  @override
  Future<void> disconnect() async {}

  @override
  Future<RobotDiscoveredDevice> readRobotInfo() async => _robot();

  @override
  Future<ProvisioningStatus> readWifiStatus() async {
    return const ProvisioningStatus(state: WifiProvisioningState.idle);
  }

  @override
  Future<List<WifiNetwork>> scanWifiNetworks() async => const [];

  @override
  Future<void> sendWifiCredentials({
    required String ssid,
    required String password,
    String country = 'LK',
  }) async {}

  void dispose() {
    _statusController.close();
  }
}
