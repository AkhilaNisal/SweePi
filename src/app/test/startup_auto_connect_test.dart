import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sweepi/core/connection/robot_channel.dart';
import 'package:sweepi/core/connection/robot_connection_manager.dart';
import 'package:sweepi/core/connection/robot_connection_state.dart';
import 'package:sweepi/core/connection/robot_discovered_device.dart';
import 'package:sweepi/core/discovery/ble_robot_discovery_service.dart';
import 'package:sweepi/core/discovery/mdns_robot_discovery_service.dart';
import 'package:sweepi/features/app/app_controller.dart';
import 'package:sweepi/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('startup auto-connect succeeds with saved reachable API host', () async {
    final server = await _FakeRobotApiServer.start();
    addTearDown(server.close);
    SharedPreferences.setMockInitialValues({
      _savedRobotPreferenceKey: jsonEncode(
        _savedRobot(server.port).toPersistenceJson(),
      ),
    });
    final controller = AppController();
    addTearDown(controller.dispose);
    await controller.initialize();

    await controller.startupAutoConnect(
      healthTimeout: const Duration(milliseconds: 200),
      savedRobotRetryWindow: Duration.zero,
      discoveredRobotRetryWindow: Duration.zero,
    );

    expect(controller.isConnected, isTrue);
    expect(controller.robotStatus.robotId, 'sweepi-8f23');
    expect(controller.lastMessage, 'Connected to SweePi');
    expect(
      controller.connectionManager.state.status,
      RobotConnectionStatus.connected,
    );

    final preferences = await SharedPreferences.getInstance();
    final saved =
        jsonDecode(preferences.getString(_savedRobotPreferenceKey)!)
            as Map<String, dynamic>;
    expect(saved['last_known_api_host'], InternetAddress.loopbackIPv4.address);
    expect(saved['api_port'], server.port);
    expect(saved['last_successful_connection_at'], isNotNull);
  });

  testWidgets('startup does not show Wi-Fi setup when health succeeds', (
    tester,
  ) async {
    final server = await _FakeRobotApiServer.start();
    addTearDown(server.close);
    SharedPreferences.setMockInitialValues({
      _savedRobotPreferenceKey: jsonEncode(
        _savedRobot(server.port).toPersistenceJson(),
      ),
    });
    final controller = AppController();
    addTearDown(controller.dispose);
    await controller.initialize();
    await controller.startupAutoConnect(
      healthTimeout: const Duration(milliseconds: 200),
      savedRobotRetryWindow: Duration.zero,
      discoveredRobotRetryWindow: Duration.zero,
    );

    await tester.pumpWidget(SweePiApp(controller: controller));
    await tester.pumpAndSettle();

    expect(find.text('Robot Dashboard'), findsOneWidget);
    expect(find.text('Choose a Wi-Fi network'), findsNothing);
    expect(find.text('Set up new SweePi'), findsNothing);
  });

  testWidgets('startup falls back to discovery/setup when saved host fails', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({
      _savedRobotPreferenceKey: jsonEncode(_savedRobot(9).toPersistenceJson()),
    });
    final controller = AppController(
      connectionManager: RobotConnectionManager(
        mdnsDiscoveryService: const MockMdnsRobotDiscoveryService(
          shouldFindRobot: false,
        ),
        bleDiscoveryService: const MockBleRobotDiscoveryService(),
      ),
    );
    addTearDown(controller.dispose);
    await controller.initialize();

    await controller.startupAutoConnect(
      healthTimeout: const Duration(milliseconds: 50),
      savedRobotRetryWindow: Duration.zero,
      discoveredRobotRetryWindow: Duration.zero,
    );
    await tester.pumpWidget(SweePiApp(controller: controller));
    await tester.pumpAndSettle();

    expect(controller.isConnected, isFalse);
    expect(
      controller.errorMessage,
      AppController.startupConnectionFailureMessage,
    );
    expect(
      find.textContaining('Could not reach SweePi over Wi-Fi'),
      findsOneWidget,
    );
    expect(find.text('Set up'), findsOneWidget);
  });
}

const _savedRobotPreferenceKey = 'selected_robot_identity';

RobotDiscoveredDevice _savedRobot(int apiPort) {
  return RobotDiscoveredDevice(
    robotId: 'sweepi-8f23',
    name: 'SweePi-8F23',
    channel: RobotChannel.wifi,
    ipAddress: InternetAddress.loopbackIPv4.address,
    apiPort: apiPort,
    websocketPort: 8765,
    lastKnownWifiSsid: 'Home WiFi',
  );
}

class _FakeRobotApiServer {
  _FakeRobotApiServer(this._server);

  final HttpServer _server;

  int get port => _server.port;

  static Future<_FakeRobotApiServer> start() async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final fake = _FakeRobotApiServer(server);
    fake._listen();
    return fake;
  }

  void _listen() {
    _server.listen((request) async {
      final payload = switch (request.uri.path) {
        '/api/system/health' => {'success': true, 'status': 'ok'},
        '/api/robot/status' => {
          'success': true,
          'robot_id': 'sweepi-8f23',
          'state': 'idle',
          'mode': 'automatic',
          'battery': {'percent': 91, 'charging': false},
          'nav': {'execution_status': 'IDLE'},
          'errors': <String>[],
          'warnings': <String>[],
        },
        '/api/exploration/status' => {
          'success': true,
          'active': false,
          'state': 'idle',
          'mode': 'automatic',
        },
        '/api/maps' => {'success': true, 'items': <Object>[]},
        _ => {
          'success': false,
          'message': 'Unexpected path: ${request.uri.path}',
        },
      };
      request.response.headers.contentType = ContentType.json;
      if (payload['success'] == false) {
        request.response.statusCode = HttpStatus.notFound;
      }
      request.response.write(jsonEncode(payload));
      await request.response.close();
    });
  }

  Future<void> close() async {
    await _server.close(force: true);
  }
}
