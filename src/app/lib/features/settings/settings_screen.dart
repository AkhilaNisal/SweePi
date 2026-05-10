import 'package:flutter/material.dart';

import '../app/app_controller.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _hostController;
  late final TextEditingController _apiPortController;
  late final TextEditingController _wsPortController;

  @override
  void initState() {
    super.initState();
    _hostController = TextEditingController(text: widget.controller.host);
    _apiPortController = TextEditingController(
      text: widget.controller.apiPort.toString(),
    );
    _wsPortController = TextEditingController(
      text: widget.controller.wsPort.toString(),
    );
  }

  @override
  void dispose() {
    _hostController.dispose();
    _apiPortController.dispose();
    _wsPortController.dispose();
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
                  'LAN Connection',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _hostController,
                  decoration: const InputDecoration(labelText: 'Raspberry Pi host'),
                  onChanged: widget.controller.updateHost,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _apiPortController,
                  decoration: const InputDecoration(labelText: 'API port'),
                  keyboardType: TextInputType.number,
                  onChanged: widget.controller.updateApiPort,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _wsPortController,
                  decoration: const InputDecoration(labelText: 'WebSocket port'),
                  keyboardType: TextInputType.number,
                  onChanged: widget.controller.updateWsPort,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  children: [
                    FilledButton(
                      onPressed: widget.controller.isBusy
                          ? null
                          : widget.controller.connect,
                      child: const Text('Connect'),
                    ),
                    OutlinedButton(
                      onPressed: widget.controller.isBusy
                          ? null
                          : widget.controller.refreshAll,
                      child: const Text('Refresh'),
                    ),
                    OutlinedButton(
                      onPressed: widget.controller.isBusy
                          ? null
                          : widget.controller.disconnect,
                      child: const Text('Disconnect'),
                    ),
                  ],
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
                const Text(
                  'The app currently uses direct LAN connectivity through your '
                  'Wi-Fi router. Discovery is still manual in this implementation, '
                  'so enter the Raspberry Pi host and ports here before connecting.',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
