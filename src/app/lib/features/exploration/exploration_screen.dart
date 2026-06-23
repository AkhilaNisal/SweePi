import 'package:flutter/material.dart';

import '../app/app_controller.dart';

class ExplorationScreen extends StatefulWidget {
  const ExplorationScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<ExplorationScreen> createState() => _ExplorationScreenState();
}

class _ExplorationScreenState extends State<ExplorationScreen> {
  final TextEditingController _mapNameController = TextEditingController(
    text: 'bedroom',
  );
  String _mode = 'automatic';
  double _speed = 0.2;

  @override
  void dispose() {
    _mapNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final status = controller.explorationStatus;
    final isManual = _mode == 'manual' || status.mode == 'manual';
    final isExploring = controller.isExploring;

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
                  'Exploration',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _mapNameController,
                  decoration: const InputDecoration(
                    labelText: 'Map or area name',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(
                      value: 'automatic',
                      label: Text('Automatic'),
                      icon: Icon(Icons.auto_mode),
                    ),
                    ButtonSegment(
                      value: 'manual',
                      label: Text('Manual'),
                      icon: Icon(Icons.gamepad_outlined),
                    ),
                  ],
                  selected: {_mode},
                  onSelectionChanged: controller.isBusy
                      ? null
                      : (values) => setState(() => _mode = values.first),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: SizedBox(
                        height: 52,
                        child: FilledButton.icon(
                          onPressed: controller.isBusy
                              ? null
                              : () {
                                  if (isExploring) {
                                    controller.stopExploration();
                                  } else {
                                    controller.startExploration(
                                      _mapNameController.text,
                                      _mode,
                                    );
                                  }
                                },
                          icon: Icon(
                            isExploring
                                ? Icons.stop_rounded
                                : Icons.play_arrow_rounded,
                          ),
                          label: Text(isExploring ? 'Stop' : 'Start'),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    SizedBox(
                      width: 56,
                      height: 52,
                      child: IconButton.filledTonal(
                        tooltip: 'Refresh state',
                        onPressed: controller.isBusy
                            ? null
                            : controller.refreshExplorationStatus,
                        icon: const Icon(Icons.refresh_rounded),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Exploration Status',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text('State: ${status.state}'),
                Text('Mode: ${status.mode}'),
                Text('Map name: ${status.mapName ?? 'None'}'),
                Text('Map available: ${status.mapAvailable ? 'Yes' : 'No'}'),
                Text('Message: ${status.message}'),
                Text(
                  'Last saved map ID: ${controller.lastSavedMapId ?? 'None'}',
                ),
              ],
            ),
          ),
        ),
        if (isManual) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Manual Drive',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Text('Speed: ${_speed.toStringAsFixed(2)}'),
                  Slider(
                    value: _speed,
                    min: 0,
                    max: 1,
                    divisions: 10,
                    label: _speed.toStringAsFixed(1),
                    onChanged: controller.isBusy
                        ? null
                        : (value) => setState(() => _speed = value),
                  ),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      _DriveButton(
                        label: 'Forward',
                        command: 'forward',
                        controller: controller,
                        speed: _speed,
                      ),
                      _DriveButton(
                        label: 'Backward',
                        command: 'backward',
                        controller: controller,
                        speed: _speed,
                      ),
                      _DriveButton(
                        label: 'Rotate Left',
                        command: 'rotate_left',
                        controller: controller,
                        speed: _speed,
                      ),
                      _DriveButton(
                        label: 'Rotate Right',
                        command: 'rotate_right',
                        controller: controller,
                        speed: _speed,
                      ),
                      _DriveButton(
                        label: 'Stop',
                        command: 'stop',
                        controller: controller,
                        speed: _speed,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _DriveButton extends StatelessWidget {
  const _DriveButton({
    required this.label,
    required this.command,
    required this.controller,
    required this.speed,
  });

  final String label;
  final String command;
  final AppController controller;
  final double speed;

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonal(
      onPressed: controller.isBusy
          ? null
          : () => controller.sendManualDrive(command, speed),
      child: Text(label),
    );
  }
}
