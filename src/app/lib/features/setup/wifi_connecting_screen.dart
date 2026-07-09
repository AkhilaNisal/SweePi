import 'package:flutter/material.dart';

import '../../core/connection/robot_channel.dart';
import '../../core/connection/robot_discovered_device.dart';
import '../../core/provisioning/ble_wifi_provisioning_service.dart';
import '../app/app_controller.dart';
import 'setup_success_screen.dart';

class WifiConnectingScreen extends StatefulWidget {
  const WifiConnectingScreen({
    super.key,
    required this.controller,
    required this.robot,
    required this.ssid,
    required this.password,
    required this.provisioningService,
  });

  final AppController controller;
  final RobotDiscoveredDevice robot;
  final String ssid;
  final String password;
  final BleWifiProvisioningService provisioningService;

  @override
  State<WifiConnectingScreen> createState() => _WifiConnectingScreenState();
}

class _WifiConnectingScreenState extends State<WifiConnectingScreen> {
  String _message = 'Connecting to your Wi-Fi...';
  String? _error;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    widget.controller.connectionManager.markProvisioning();
    try {
      await widget.provisioningService.sendWifiCredentials(
        ssid: widget.ssid,
        password: widget.password,
      );
      final status = await widget.provisioningService.readWifiStatus();
      if (!mounted) {
        return;
      }
      if (!status.isConnected) {
        setState(() {
          _error = status.message ?? 'SweePi could not join this Wi-Fi.';
        });
        return;
      }
      setState(() => _message = 'Switching to Wi-Fi connection...');
      await widget.controller.connectionManager.discoverRobots();
      final discovered = widget
          .controller
          .connectionManager
          .state
          .discoveredRobots
          .where((robot) => robot.hasWifi)
          .where(
            (robot) =>
                robot.robotId == status.robotId ||
                robot.robotId == widget.robot.robotId,
          );
      if (discovered.isNotEmpty) {
        await widget.controller.connectToDiscoveredRobot(discovered.first);
      } else if (status.hostname != null || status.ip != null) {
        await widget.controller.connectToTemporaryRobotFallback(
          RobotDiscoveredDevice(
            robotId: status.robotId ?? widget.robot.robotId,
            name: widget.robot.name,
            channel: RobotChannel.wifi,
            hostName: status.hostname,
            ipAddress: status.ip,
            apiPort: 8080,
            websocketPort: 8765,
            model: widget.robot.model,
          ),
        );
      } else {
        setState(() {
          _error =
              'Robot connected to Wi-Fi, but automatic discovery failed. Make sure your phone is on the same Wi-Fi network.';
        });
        return;
      }
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => SetupSuccessScreen(controller: widget.controller),
        ),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = '$error');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Connecting')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: _error == null
              ? Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 16),
                    Text(_message),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.info_outline,
                      size: 48,
                      color: Theme.of(context).colorScheme.error,
                    ),
                    const SizedBox(height: 16),
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Back to Wi-Fi setup'),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}
