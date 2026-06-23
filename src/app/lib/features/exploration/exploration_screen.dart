import 'dart:async';

import 'package:flutter/material.dart';

import '../app/app_controller.dart';

const _manualDriveRepeatInterval = Duration(milliseconds: 200);
const _holdMovementCommands = {
  'forward',
  'backward',
  'rotate_left',
  'rotate_right',
};

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

class _RcController extends StatefulWidget {
  const _RcController({required this.controller, required this.speed});

  final AppController controller;
  final double speed;

  @override
  State<_RcController> createState() => _RcControllerState();
}

class _RcControllerState extends State<_RcController> {
  Timer? _repeatTimer;
  String? _heldCommand;
  bool _requestInFlight = false;

  @override
  void dispose() {
    _repeatTimer?.cancel();
    _repeatTimer = null;
    _heldCommand = null;
    super.dispose();
  }

  void _startHolding(String command) {
    if (!_holdMovementCommands.contains(command) ||
        _heldCommand != null ||
        widget.controller.isBusy) {
      return;
    }

    setState(() => _heldCommand = command);
    _sendHeldCommand(command);
    _repeatTimer = Timer.periodic(
      _manualDriveRepeatInterval,
      (_) => _sendHeldCommand(command),
    );
  }

  void _stopHolding() {
    _repeatTimer?.cancel();
    _repeatTimer = null;

    if (!mounted || _heldCommand == null) {
      _heldCommand = null;
      return;
    }

    setState(() => _heldCommand = null);
  }

  Future<void> _sendHeldCommand(String command) async {
    if (_requestInFlight || _heldCommand != command) {
      return;
    }

    _requestInFlight = true;
    try {
      await widget.controller.sendManualDrive(command, widget.speed);
    } finally {
      _requestInFlight = false;
    }
  }

  Future<void> _sendStop() async {
    if (_heldCommand != null || widget.controller.isBusy) {
      return;
    }
    await widget.controller.sendManualDrive('stop', widget.speed);
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final heldCommand = _heldCommand;

    bool enabledFor(String command) {
      if (widget.controller.isBusy) {
        return false;
      }
      return heldCommand == null || heldCommand == command;
    }

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
              icon: Icons.arrow_upward_rounded,
              enabled: enabledFor('forward'),
              active: heldCommand == 'forward',
              onHoldStart: () => _startHolding('forward'),
              onHoldEnd: _stopHolding,
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
                  icon: Icons.rotate_left_rounded,
                  enabled: enabledFor('rotate_left'),
                  active: heldCommand == 'rotate_left',
                  onHoldStart: () => _startHolding('rotate_left'),
                  onHoldEnd: _stopHolding,
                ),
              ),
              const SizedBox(width: 14),
              SizedBox.square(
                dimension: 92,
                child: _DriveButton(
                  tooltip: 'Stop',
                  icon: Icons.stop_rounded,
                  enabled: enabledFor('stop'),
                  active: false,
                  backgroundColor: colorScheme.errorContainer,
                  foregroundColor: colorScheme.onErrorContainer,
                  onTap: _sendStop,
                ),
              ),
              const SizedBox(width: 14),
              SizedBox.square(
                dimension: 88,
                child: _DriveButton(
                  tooltip: 'Rotate right',
                  icon: Icons.rotate_right_rounded,
                  enabled: enabledFor('rotate_right'),
                  active: heldCommand == 'rotate_right',
                  onHoldStart: () => _startHolding('rotate_right'),
                  onHoldEnd: _stopHolding,
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
              icon: Icons.arrow_downward_rounded,
              enabled: enabledFor('backward'),
              active: heldCommand == 'backward',
              onHoldStart: () => _startHolding('backward'),
              onHoldEnd: _stopHolding,
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
    required this.icon,
    required this.enabled,
    required this.active,
    this.backgroundColor,
    this.foregroundColor,
    this.onTap,
    this.onHoldStart,
    this.onHoldEnd,
  });

  final String tooltip;
  final IconData icon;
  final bool enabled;
  final bool active;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final VoidCallback? onTap;
  final VoidCallback? onHoldStart;
  final VoidCallback? onHoldEnd;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(26),
    );
    final isHoldButton = onHoldStart != null && onHoldEnd != null;
    final effectiveBackground = !enabled
        ? colorScheme.surfaceContainerHighest
        : active
        ? colorScheme.primary
        : backgroundColor ?? colorScheme.primaryContainer;
    final effectiveForeground = !enabled
        ? colorScheme.onSurfaceVariant.withValues(alpha: 0.54)
        : active
        ? colorScheme.onPrimary
        : foregroundColor ?? colorScheme.onPrimaryContainer;

    return Tooltip(
      message: tooltip,
      child: Listener(
        onPointerDown: enabled && isHoldButton ? (_) => onHoldStart!() : null,
        onPointerUp: isHoldButton ? (_) => onHoldEnd!() : null,
        onPointerCancel: isHoldButton ? (_) => onHoldEnd!() : null,
        child: Material(
          color: effectiveBackground,
          shape: shape,
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: enabled && !isHoldButton ? onTap : null,
            customBorder: shape,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 110),
              curve: Curves.easeOut,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(26),
                border: active
                    ? Border.all(color: colorScheme.primary, width: 2)
                    : null,
                boxShadow: active
                    ? [
                        BoxShadow(
                          color: colorScheme.primary.withValues(alpha: 0.24),
                          blurRadius: 14,
                          spreadRadius: 1,
                        ),
                      ]
                    : null,
              ),
              child: Center(
                child: Icon(icon, size: 38, color: effectiveForeground),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
