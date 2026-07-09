import 'package:flutter/material.dart';

import '../../core/connection/robot_channel.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/sweepi_widgets.dart';
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
    final state = widget.controller.connectionManager.state;
    return AppBackground(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 104),
        children: [
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  title: 'Appearance',
                  subtitle: 'Choose the dashboard style that fits your room.',
                  icon: Icons.palette_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
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
          const SizedBox(height: SweePiSpacing.md),
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'Robot Connection',
                  subtitle: state.message ?? 'Manage setup and recovery.',
                  icon: Icons.wifi_tethering_rounded,
                  trailing: StatusChip(
                    label: widget.controller.isConnected ? 'Online' : 'Offline',
                    icon: widget.controller.isConnected
                        ? Icons.cloud_done_rounded
                        : Icons.cloud_off_rounded,
                    color: widget.controller.isConnected
                        ? SweePiColors.secondary
                        : SweePiColors.danger,
                  ),
                ),
                const SizedBox(height: SweePiSpacing.md),
                _SettingsTile(
                  icon: Icons.wifi_rounded,
                  color: SweePiColors.primary,
                  title: 'Robot Wi-Fi',
                  subtitle: state.message ?? 'Manage setup and recovery.',
                  trailing: const Icon(Icons.chevron_right_rounded),
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
                const SizedBox(height: SweePiSpacing.sm),
                _SettingsTile(
                  icon: Icons.search_rounded,
                  color: SweePiColors.secondary,
                  title: 'Discover SweePi',
                  subtitle: 'Search Wi-Fi and Bluetooth.',
                  trailing: state.isScanning
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : null,
                  onTap: state.isScanning
                      ? null
                      : widget.controller.startRobotDiscovery,
                ),
              ],
            ),
          ),
          const SizedBox(height: SweePiSpacing.md),
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  title: 'Connection Details',
                  subtitle: 'Robot, channel, and API endpoint information.',
                  icon: Icons.settings_ethernet_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
                Wrap(
                  spacing: SweePiSpacing.sm,
                  runSpacing: SweePiSpacing.sm,
                  children: [
                    StatusChip(
                      label:
                          state.selectedRobot?.robotId ?? 'No robot selected',
                      icon: Icons.smart_toy_rounded,
                      color: SweePiColors.primary,
                    ),
                    StatusChip(
                      label: state.channel.label,
                      icon: Icons.cable_rounded,
                      color: SweePiColors.secondary,
                    ),
                  ],
                ),
                const SizedBox(height: SweePiSpacing.md),
                _DetailLine(
                  label: 'Base URL',
                  value:
                      'http://${widget.controller.host}:${widget.controller.apiPort}',
                ),
                _DetailLine(
                  label: 'mDNS services',
                  value: state.debugMdnsServices.isEmpty
                      ? 'None'
                      : state.debugMdnsServices.join(', '),
                ),
                _DetailLine(
                  label: 'BLE devices',
                  value: state.debugBleDevices.isEmpty
                      ? 'None'
                      : state.debugBleDevices.join(', '),
                ),
                const SizedBox(height: SweePiSpacing.md),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Developer manual connection'),
                  subtitle: const Text('For mock API server development only.'),
                  children: [
                    TextField(
                      controller: _hostController,
                      decoration: const InputDecoration(labelText: 'Host'),
                      onChanged: widget.controller.updateHost,
                    ),
                    const SizedBox(height: SweePiSpacing.md),
                    TextField(
                      controller: _apiPortController,
                      decoration: const InputDecoration(labelText: 'API port'),
                      keyboardType: TextInputType.number,
                      onChanged: widget.controller.updateApiPort,
                    ),
                    const SizedBox(height: SweePiSpacing.md),
                    Wrap(
                      spacing: SweePiSpacing.md,
                      runSpacing: SweePiSpacing.md,
                      children: [
                        FilledButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.connect,
                          icon: const Icon(Icons.link_rounded),
                          label: const Text('Connect'),
                        ),
                        OutlinedButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.refreshRobotStatus,
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('Refresh Status'),
                        ),
                        OutlinedButton.icon(
                          onPressed: widget.controller.isBusy
                              ? null
                              : widget.controller.disconnect,
                          icon: const Icon(Icons.link_off_rounded),
                          label: const Text('Disconnect'),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  const _SettingsTile({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.trailing,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(SweePiRadius.md),
        ),
        child: Icon(icon, color: color),
      ),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(subtitle),
      trailing: trailing,
      onTap: onTap,
    );
  }
}

class _DetailLine extends StatelessWidget {
  const _DetailLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: SweePiSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
