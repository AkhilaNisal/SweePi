import 'package:flutter/material.dart';

import '../../core/connection/robot_discovered_device.dart';
import '../app/app_controller.dart';
import '../setup/bluetooth_pairing_screen.dart';

class RobotWifiSettingsScreen extends StatelessWidget {
  const RobotWifiSettingsScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final connection = controller.connectionManager.state;
    final selected = connection.selectedRobot;
    RobotDiscoveredDevice? bleRobot;
    for (final robot in connection.discoveredRobots) {
      if (robot.hasBluetooth) {
        bleRobot = robot;
        break;
      }
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Robot Wi-Fi')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            selected?.name ?? 'SweePi',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(connection.message ?? 'Manage your robot connection.'),
          const SizedBox(height: 16),
          if (controller.isConnected && selected != null)
            _ActionCard(
              title: 'Change Wi-Fi',
              body:
                  'SweePi is reachable over Wi-Fi. Bluetooth may be used as the setup channel to change networks.',
              actionLabel: 'Change Wi-Fi',
              icon: Icons.wifi,
              onPressed: bleRobot == null
                  ? controller.startRobotDiscovery
                  : () => _openBluetoothSetup(context, bleRobot!),
            )
          else if (bleRobot != null)
            _ActionCard(
              title: 'Recover or change Wi-Fi',
              body:
                  'SweePi is nearby over Bluetooth. Send new Wi-Fi credentials to recover the connection.',
              actionLabel: 'Recover Wi-Fi',
              icon: Icons.bluetooth,
              onPressed: () => _openBluetoothSetup(context, bleRobot!),
            )
          else
            _ActionCard(
              title: 'No robot found',
              body:
                  'Power on SweePi or press its setup button, then search again.',
              actionLabel: 'Search for SweePi',
              icon: Icons.search,
              onPressed: controller.startRobotDiscovery,
            ),
        ],
      ),
    );
  }

  void _openBluetoothSetup(BuildContext context, RobotDiscoveredDevice robot) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            BluetoothPairingScreen(controller: controller, robot: robot),
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.title,
    required this.body,
    required this.actionLabel,
    required this.icon,
    required this.onPressed,
  });

  final String title;
  final String body;
  final String actionLabel;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 32),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(body),
            const SizedBox(height: 16),
            FilledButton(onPressed: onPressed, child: Text(actionLabel)),
          ],
        ),
      ),
    );
  }
}
