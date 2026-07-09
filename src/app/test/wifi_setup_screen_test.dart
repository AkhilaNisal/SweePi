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
  test('connect block reason covers BLE and Wi-Fi form readiness', () {
    const secureNetwork = WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2');

    expect(
      wifiConnectBlockReason(
        bleConnected: false,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      WifiConnectBlockReason.bleNotConnected,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: false,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      WifiConnectBlockReason.provisioningServiceNotFound,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: false,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      WifiConnectBlockReason.wifiConfigCharacteristicNotFound,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: '',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: false,
      ),
      WifiConnectBlockReason.ssidMissing,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: '',
        selectedNetwork: null,
        isConnecting: false,
      ),
      WifiConnectBlockReason.passwordMissing,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: null,
        isConnecting: false,
      ),
      WifiConnectBlockReason.none,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'guest',
        password: '',
        selectedNetwork: const WifiNetwork(ssid: 'guest', security: 'open'),
        isConnecting: false,
      ),
      WifiConnectBlockReason.none,
    );
    expect(
      wifiConnectBlockReason(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: secureNetwork,
        isConnecting: true,
      ),
      WifiConnectBlockReason.connecting,
    );
    expect(
      connectBlockReasonMessage(WifiConnectBlockReason.connecting),
      'Connecting to Wi-Fi...',
    );
  });

  test('canConnectToWifi is true only when block reason is none', () {
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: true,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: null,
        isConnecting: false,
      ),
      isTrue,
    );
    expect(
      canConnectToWifi(
        bleConnected: true,
        provisioningServiceDiscovered: true,
        wifiConfigDiscovered: false,
        ssid: 'akhila',
        password: 'password',
        selectedNetwork: null,
        isConnecting: false,
      ),
      isFalse,
    );
  });

  testWidgets('BLE disconnected reason is visible', (tester) async {
    final service = _FakeProvisioningService(isConnected: false);
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);

    expect(_connectButton(tester).onPressed, isNull);
    expect(find.text('Bluetooth device is not connected.'), findsOneWidget);
  });

  testWidgets('provisioning service missing reason is visible', (tester) async {
    final service = _FakeProvisioningService(
      isProvisioningServiceDiscovered: false,
    );
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);

    expect(_connectButton(tester).onPressed, isNull);
    expect(
      find.text('SweePi BLE provisioning service was not discovered.'),
      findsOneWidget,
    );
  });

  testWidgets('WIFI_CONFIG missing reason is visible', (tester) async {
    final service = _FakeProvisioningService(
      hasWifiConfigCharacteristic: false,
    );
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_ssidField(), 'akhila');
    await tester.enterText(_passwordField(), 'password');
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNull);
    expect(
      find.text('Wi-Fi config characteristic was not found.'),
      findsOneWidget,
    );
  });

  testWidgets('SSID missing reason is visible', (tester) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);

    expect(_connectButton(tester).onPressed, isNull);
    expect(find.text('Enter a Wi-Fi network name.'), findsOneWidget);
  });

  testWidgets('manual secured network password missing reason is visible', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_ssidField(), 'manual-network');
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNull);
    expect(find.text('Enter the Wi-Fi password.'), findsOneWidget);
  });

  testWidgets('manual SSID and password enables button and hides reason', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_ssidField(), 'manual-network');
    await tester.enterText(_passwordField(), 'password');
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
    expect(find.text('Enter the Wi-Fi password.'), findsNothing);
    expect(find.text('Enter a Wi-Fi network name.'), findsNothing);
  });

  testWidgets('scanned secured network with password enables button', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(
      tester,
      service: service,
      networks: const [WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2')],
    );
    await tester.enterText(_passwordField(), 'password');
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
  });

  testWidgets('scanned open network without password enables button', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(
      tester,
      service: service,
      networks: const [
        WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2'),
        WifiNetwork(ssid: 'guest', security: 'open'),
      ],
    );
    await tester.tap(find.text('guest'));
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
  });

  testWidgets('SSID text change updates reason immediately', (tester) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_passwordField(), 'password');
    await tester.pump();
    expect(find.text('Enter a Wi-Fi network name.'), findsOneWidget);

    await tester.enterText(_ssidField(), 'manual-network');
    await tester.pump();
    expect(_connectButton(tester).onPressed, isNotNull);

    await tester.enterText(_ssidField(), '');
    await tester.pump();
    expect(find.text('Enter a Wi-Fi network name.'), findsOneWidget);
  });

  testWidgets('password text change updates reason immediately', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_ssidField(), 'manual-network');
    await tester.pump();
    expect(find.text('Enter the Wi-Fi password.'), findsOneWidget);

    await tester.enterText(_passwordField(), 'password');
    await tester.pump();
    expect(_connectButton(tester).onPressed, isNotNull);

    await tester.enterText(_passwordField(), '');
    await tester.pump();
    expect(find.text('Enter the Wi-Fi password.'), findsOneWidget);
  });

  testWidgets(
    'manual SSID edit clears scanned selection and treats it as secured',
    (tester) async {
      final service = _FakeProvisioningService();
      addTearDown(service.dispose);

      await _pumpWifiSetup(
        tester,
        service: service,
        networks: const [WifiNetwork(ssid: 'guest', security: 'open')],
      );
      expect(_connectButton(tester).onPressed, isNotNull);

      await tester.enterText(_ssidField(), 'custom-secured-network');
      await tester.pump();
      expect(find.text('Enter the Wi-Fi password.'), findsOneWidget);

      await tester.enterText(_passwordField(), 'password');
      await tester.pump();
      expect(_connectButton(tester).onPressed, isNotNull);
    },
  );

  testWidgets('BLE readiness change updates reason immediately', (
    tester,
  ) async {
    final service = _FakeProvisioningService(
      isConnected: false,
      isProvisioningServiceDiscovered: false,
      hasWifiConfigCharacteristic: false,
    );
    addTearDown(service.dispose);

    await _pumpWifiSetup(tester, service: service);
    await tester.enterText(_ssidField(), 'manual-network');
    await tester.enterText(_passwordField(), 'password');
    await tester.pump();
    expect(find.text('Bluetooth device is not connected.'), findsOneWidget);

    service.updateReadiness(
      isConnected: true,
      isProvisioningServiceDiscovered: true,
      hasWifiConfigCharacteristic: true,
    );
    await tester.pump();

    expect(_connectButton(tester).onPressed, isNotNull);
  });

  testWidgets('debug details show state without revealing password', (
    tester,
  ) async {
    final service = _FakeProvisioningService();
    addTearDown(service.dispose);

    await _pumpWifiSetup(
      tester,
      service: service,
      networks: const [WifiNetwork(ssid: 'akhila', security: 'WPA/WPA2')],
    );
    await tester.enterText(_passwordField(), 'secret-password');
    await tester.tap(find.text('Debug details'));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView), const Offset(0, -300));
    await tester.pump();

    expect(
      find.text('BLE connected: true', skipOffstage: false),
      findsOneWidget,
    );
    expect(
      find.text('WIFI_CONFIG discovered: true', skipOffstage: false),
      findsOneWidget,
    );
    expect(
      find.text('Selected network: akhila', skipOffstage: false),
      findsOneWidget,
    );
    expect(find.text('SSID text: akhila', skipOffstage: false), findsOneWidget);
    expect(
      find.text('Password length: 15', skipOffstage: false),
      findsOneWidget,
    );
    expect(
      find.byWidgetPredicate(
        (widget) =>
            widget is Text &&
            (widget.data?.contains('secret-password') ?? false),
      ),
      findsNothing,
    );
  });
}

Future<void> _pumpWifiSetup(
  WidgetTester tester, {
  required _FakeProvisioningService service,
  List<WifiNetwork> networks = const [],
}) async {
  final controller = AppController();
  addTearDown(controller.dispose);

  await tester.pumpWidget(
    MaterialApp(
      home: WifiSetupScreen(
        controller: controller,
        robot: _robot(),
        networks: networks,
        provisioningService: service,
      ),
    ),
  );
}

Finder _ssidField() {
  return find.byType(TextField).first;
}

Finder _passwordField() {
  return find.byType(TextField).last;
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
  _FakeProvisioningService({
    this.isConnected = true,
    this.isProvisioningServiceDiscovered = true,
    this.hasWifiConfigCharacteristic = true,
  });

  final _statusController = StreamController<ProvisioningStatus>.broadcast();

  @override
  Stream<ProvisioningStatus> get statusStream => _statusController.stream;

  @override
  bool isConnected;

  @override
  bool isProvisioningServiceDiscovered;

  @override
  bool hasWifiConfigCharacteristic;

  void updateReadiness({
    required bool isConnected,
    required bool isProvisioningServiceDiscovered,
    required bool hasWifiConfigCharacteristic,
  }) {
    this.isConnected = isConnected;
    this.isProvisioningServiceDiscovered = isProvisioningServiceDiscovered;
    this.hasWifiConfigCharacteristic = hasWifiConfigCharacteristic;
    _statusController.add(
      const ProvisioningStatus(state: WifiProvisioningState.idle),
    );
  }

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
