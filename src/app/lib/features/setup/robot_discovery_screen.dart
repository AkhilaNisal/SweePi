import 'package:flutter/material.dart';

import '../../core/connection/robot_connection_state.dart';
import '../../core/connection/robot_discovered_device.dart';
import '../app/app_controller.dart';
import 'bluetooth_pairing_screen.dart';

class RobotDiscoveryScreen extends StatelessWidget {
  const RobotDiscoveryScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final connectionState = controller.connectionManager.state;
    final robots = connectionState.discoveredRobots;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          connectionState.message ?? 'Searching for SweePi...',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          _supportingText(connectionState.status),
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: connectionState.isScanning || controller.isBusy
              ? null
              : controller.startRobotDiscovery,
          icon: connectionState.isScanning
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.search),
          label: Text(
            connectionState.isScanning ? 'Searching...' : 'Search again',
          ),
        ),
        const SizedBox(height: 16),
        if (robots.isEmpty) _NoRobotCard(controller: controller),
        for (final robot in robots)
          _RobotTile(controller: controller, robot: robot),
      ],
    );
  }

  String _supportingText(RobotConnectionStatus status) {
    switch (status) {
      case RobotConnectionStatus.scanning:
        return 'Looking on your Wi-Fi and nearby Bluetooth devices.';
      case RobotConnectionStatus.noRobotFound:
      case RobotConnectionStatus.discoveryFailed:
        return 'Power on your robot or press its setup button, then start setup.';
      case RobotConnectionStatus.bleFound:
        return 'Use Bluetooth to set up or recover Wi-Fi.';
      case RobotConnectionStatus.wifiFound:
      case RobotConnectionStatus.bothFound:
      case RobotConnectionStatus.wifiConnected:
      case RobotConnectionStatus.connected:
        return 'Wi-Fi will be used for maps, cleaning, telemetry, and status.';
      case RobotConnectionStatus.bleConnected:
      case RobotConnectionStatus.provisioning:
      case RobotConnectionStatus.wifiConnecting:
        return 'Setup is in progress.';
      case RobotConnectionStatus.error:
        return 'Check that your phone and SweePi are nearby and try again.';
    }
  }
}

class _RobotTile extends StatelessWidget {
  const _RobotTile({required this.controller, required this.robot});

  final AppController controller;
  final RobotDiscoveredDevice robot;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(robot.hasWifi ? Icons.wifi : Icons.bluetooth),
        title: Text(robot.name),
        subtitle: Text(
          [
            robot.robotId,
            robot.hasWifi && robot.hasBluetooth
                ? 'Wi-Fi and Bluetooth'
                : robot.hasWifi
                ? 'Wi-Fi'
                : 'Bluetooth',
            if (robot.status != null) robot.status!,
          ].join(' - '),
        ),
        trailing: FilledButton(
          onPressed: controller.isBusy
              ? null
              : () async {
                  if (robot.hasWifi) {
                    await controller.selectDiscoveredRobot(robot);
                    return;
                  }
                  if (!context.mounted) {
                    return;
                  }
                  await Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => BluetoothPairingScreen(
                        controller: controller,
                        robot: robot,
                      ),
                    ),
                  );
                },
          child: Text(robot.hasWifi ? 'Connect' : 'Set up'),
        ),
      ),
    );
  }
}

class _NoRobotCard extends StatelessWidget {
  const _NoRobotCard({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Set up new SweePi',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Turn on your robot and press the setup button, then search again.',
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: controller.startRobotDiscovery,
              icon: const Icon(Icons.bluetooth_searching),
              label: const Text('Find nearby SweePi'),
            ),
          ],
        ),
      ),
    );
  }
}
