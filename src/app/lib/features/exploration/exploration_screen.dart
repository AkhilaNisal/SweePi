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
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 20),
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
                  const SizedBox(height: 8),
                  Center(
                    child: _RcController(controller: controller, speed: _speed),
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

class _RcController extends StatelessWidget {
  const _RcController({required this.controller, required this.speed});

  final AppController controller;
  final double speed;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 340),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 168,
            height: 84,
            child: _DriveButton(
              tooltip: 'Forward',
              command: 'forward',
              controller: controller,
              speed: speed,
              icon: Icons.arrow_upward_rounded,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox.square(
                dimension: 88,
                child: _DriveButton(
                  tooltip: 'Rotate left',
                  command: 'rotate_left',
                  controller: controller,
                  speed: speed,
                  icon: Icons.rotate_left_rounded,
                ),
              ),
              const SizedBox(width: 14),
              SizedBox.square(
                dimension: 92,
                child: _DriveButton(
                  tooltip: 'Stop',
                  command: 'stop',
                  controller: controller,
                  speed: speed,
                  icon: Icons.stop_rounded,
                  backgroundColor: colorScheme.errorContainer,
                  foregroundColor: colorScheme.onErrorContainer,
                ),
              ),
              const SizedBox(width: 14),
              SizedBox.square(
                dimension: 88,
                child: _DriveButton(
                  tooltip: 'Rotate right',
                  command: 'rotate_right',
                  controller: controller,
                  speed: speed,
                  icon: Icons.rotate_right_rounded,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: 168,
            height: 84,
            child: _DriveButton(
              tooltip: 'Backward',
              command: 'backward',
              controller: controller,
              speed: speed,
              icon: Icons.arrow_downward_rounded,
            ),
          ),
        ],
      ),
    );
  }
}

class _DriveButton extends StatelessWidget {
  const _DriveButton({
    required this.tooltip,
    required this.command,
    required this.controller,
    required this.speed,
    required this.icon,
    this.backgroundColor,
    this.foregroundColor,
  });

  final String tooltip;
  final String command;
  final AppController controller;
  final double speed;
  final IconData icon;
  final Color? backgroundColor;
  final Color? foregroundColor;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Tooltip(
      message: tooltip,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: backgroundColor ?? colorScheme.primaryContainer,
          foregroundColor: foregroundColor ?? colorScheme.onPrimaryContainer,
          disabledBackgroundColor: colorScheme.surfaceContainerHighest,
          disabledForegroundColor: colorScheme.onSurfaceVariant,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(26),
          ),
          padding: EdgeInsets.zero,
        ),
        onPressed: controller.isBusy
            ? null
            : () => controller.sendManualDrive(command, speed),
        child: Icon(icon, size: 38),
      ),
    );
  }
}
