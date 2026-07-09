import 'package:flutter/material.dart';

import '../../core/connection/robot_channel.dart';
import '../app/app_controller.dart';
import 'robot_wifi_settings_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _hostController;
  late final TextEditingController _apiPortController;

  @override
  void initState() {
    super.initState();
    _hostController = TextEditingController(text: widget.controller.host);
    _apiPortController = TextEditingController(
      text: widget.controller.apiPort.toString(),
    );
  }

  @override
  void dispose() {
    _hostController.dispose();
    _apiPortController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Appearance',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: SegmentedButton<ThemeMode>(
                    segments: const [
                      ButtonSegment(
                        value: ThemeMode.light,
                        icon: Icon(Icons.light_mode_outlined),
                        label: Text('Light'),
                      ),
                      ButtonSegment(
                        value: ThemeMode.dark,
                        icon: Icon(Icons.dark_mode_outlined),
                        label: Text('Dark'),
                      ),
                    ],
                    selected: {widget.controller.themeMode},
                    onSelectionChanged: (values) {
                      widget.controller.setThemeMode(values.first);
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Robot Connection',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.wifi),
                  title: const Text('Robot Wi-Fi'),
                  subtitle: Text(
                    widget.controller.connectionManager.state.message ??
                        'Manage setup and recovery.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => RobotWifiSettingsScreen(
                          controller: widget.controller,
                        ),
                      ),
                    );
                  },
                ),
                const Divider(),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.search),
                  title: const Text('Discover SweePi'),
                  subtitle: const Text('Search Wi-Fi and Bluetooth.'),
                  trailing: widget.controller.connectionManager.state.isScanning
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : null,
                  onTap: widget.controller.connectionManager.state.isScanning
                      ? null
                      : widget.controller.startRobotDiscovery,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Connection Notes',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Selected robot: ${widget.controller.connectionManager.state.selectedRobot?.robotId ?? 'None'}',
                ),
                Text(
                  'Current channel: ${widget.controller.connectionManager.state.channel.label}',
                ),
                Text(
                  'Resolved host: ${widget.controller.host}:${widget.controller.apiPort}',
                ),
                const SizedBox(height: 8),
                Text(
                  'mDNS services: ${widget.controller.connectionManager.state.debugMdnsServices.join(', ')}',
                ),
                Text(
                  'BLE devices: ${widget.controller.connectionManager.state.debugBleDevices.join(', ')}',
                ),
                const SizedBox(height: 12),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Developer manual connection'),
                  subtitle: const Text('For mock API server development only.'),
                  children: [
                    TextField(
                      controller: _hostController,
                      decoration: const InputDecoration(
                        labelText: 'Host',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: widget.controller.updateHost,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _apiPortController,
                      decoration: const InputDecoration(
                        labelText: 'API port',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      onChanged: widget.controller.updateApiPort,
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        FilledButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.connect,
                          icon: const Icon(Icons.link),
                          label: const Text('Connect'),
                        ),
                        OutlinedButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.refreshRobotStatus,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Refresh Status'),
                        ),
                        OutlinedButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.disconnect,
                          icon: const Icon(Icons.link_off),
                          label: const Text('Disconnect'),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Current base URL: http://${widget.controller.host}:${widget.controller.apiPort}',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
