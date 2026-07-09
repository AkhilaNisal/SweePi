import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sweepi/core/connection/robot_channel.dart';
import 'package:sweepi/core/connection/robot_connection_manager.dart';
import 'package:sweepi/core/connection/robot_connection_state.dart';
import 'package:sweepi/core/discovery/ble_robot_discovery_service.dart';
import 'package:sweepi/core/discovery/mdns_robot_discovery_service.dart';
import 'package:sweepi/core/provisioning/ble_wifi_provisioning_service.dart';
import 'package:sweepi/core/provisioning/provisioning_status_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('mock discovery merges Wi-Fi and Bluetooth into one robot', () async {
    SharedPreferences.setMockInitialValues({});
    final manager = RobotConnectionManager(
      mdnsDiscoveryService: const MockMdnsRobotDiscoveryService(),
      bleDiscoveryService: const MockBleRobotDiscoveryService(),
    );

    final robots = await manager.discoverRobots();

    expect(robots, hasLength(1));
    expect(robots.single.robotId, 'sweepi-8f23');
    expect(robots.single.channel, RobotChannel.both);
    expect(manager.state.status, RobotConnectionStatus.bothFound);
    expect(manager.state.selectedRobot?.hasWifi, isTrue);
  });

  test(
    'mock discovery reports no robot when both channels are empty',
    () async {
      SharedPreferences.setMockInitialValues({});
      final manager = RobotConnectionManager(
        mdnsDiscoveryService: const MockMdnsRobotDiscoveryService(
          shouldFindRobot: false,
        ),
        bleDiscoveryService: const MockBleRobotDiscoveryService(
          shouldFindRobot: false,
        ),
      );

      final robots = await manager.discoverRobots();

      expect(robots, isEmpty);
      expect(manager.state.status, RobotConnectionStatus.noRobotFound);
      expect(manager.state.channel, RobotChannel.none);
    },
  );

  test('mock provisioning can report successful Wi-Fi join', () async {
    final provisioning = MockBleWifiProvisioningService();
    final robot = (await const MockBleRobotDiscoveryService().scan()).single;

    await provisioning.connect(robot);
    final networks = await provisioning.scanWifiNetworks();
    await provisioning.sendWifiCredentials(
      ssid: networks.first.ssid,
      password: 'password',
    );
    final status = await provisioning.readWifiStatus();

    expect(networks, isNotEmpty);
    expect(status.state, WifiProvisioningState.connected);
    expect(status.hostname, 'sweepi-8f23.local');
  });

  test('mock provisioning can report Wi-Fi failure', () async {
    final provisioning = MockBleWifiProvisioningService(
      shouldConnectToWifi: false,
    );
    final robot = (await const MockBleRobotDiscoveryService().scan()).single;

    await provisioning.connect(robot);
    await provisioning.sendWifiCredentials(
      ssid: 'Home WiFi',
      password: 'wrong',
    );
    final status = await provisioning.readWifiStatus();

    expect(status.state, WifiProvisioningState.failedAuth);
    expect(status.isFailure, isTrue);
  });
}
