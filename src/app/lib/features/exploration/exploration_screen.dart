import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../core/widgets/sweepi_widgets.dart';
import '../app/app_controller.dart';

const _manualDriveRepeatInterval = Duration(milliseconds: 200);
const _holdMovementCommands = {'forward', 'backward', 'left', 'right'};

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

    return AppBackground(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 104),
        children: [
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  title: 'Explore New Map',
                  subtitle:
                      'Choose a mode, name the map, then let SweePi scan.',
                  icon: Icons.explore_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
                TextField(
                  controller: _mapNameController,
                  decoration: const InputDecoration(
                    labelText: 'Map name',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: SweePiSpacing.md),
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
                      : (values) {
                          final nextMode = values.first;
                          setState(() => _mode = nextMode);
                          if (isExploring) {
                            controller.switchExplorationMode(nextMode);
                          }
                        },
                ),
                const SizedBox(height: SweePiSpacing.lg),
                if (isExploring)
                  Row(
                    children: [
                      Expanded(
                        child: ColorfulActionButton(
                          label: 'Stop and save map',
                          icon: Icons.save_rounded,
                          color: SweePiColors.danger,
                          onPressed: controller.isBusy
                              ? null
                              : controller.stopExploration,
                        ),
                      ),
                      const SizedBox(width: SweePiSpacing.md),
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
                  )
                else
                  Row(
                    children: [
                      Expanded(
                        child: ColorfulActionButton(
                          label: 'Start automatic',
                          icon: Icons.auto_mode_rounded,
                          color: SweePiColors.primary,
                          onPressed: controller.isBusy
                              ? null
                              : () {
                                  setState(() => _mode = 'automatic');
                                  controller.startExploration(
                                    _mapNameController.text,
                                    'automatic',
                                  );
                                },
                        ),
                      ),
                      const SizedBox(width: SweePiSpacing.md),
                      Expanded(
                        child: ColorfulActionButton(
                          label: 'Start manual',
                          icon: Icons.gamepad_rounded,
                          color: SweePiColors.secondary,
                          onPressed: controller.isBusy
                              ? null
                              : () {
                                  setState(() => _mode = 'manual');
                                  controller.startExploration(
                                    _mapNameController.text,
                                    'manual',
                                  );
                                },
                        ),
                      ),
                    ],
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
                  title: 'Exploration Status',
                  subtitle: status.message,
                  icon: Icons.radar_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
                Wrap(
                  spacing: SweePiSpacing.sm,
                  runSpacing: SweePiSpacing.sm,
                  children: [
                    StatusChip(
                      label: status.state,
                      icon: Icons.circle_rounded,
                      color: statusColorForText(status.state),
                    ),
                    StatusChip(
                      label: status.mode,
                      icon: Icons.tune_rounded,
                      color: status.mode == 'manual'
                          ? SweePiColors.secondary
                          : SweePiColors.primary,
                    ),
                    StatusChip(
                      label: status.mapAvailable
                          ? 'Map available'
                          : 'Map pending',
                      icon: status.mapAvailable
                          ? Icons.map_rounded
                          : Icons.hourglass_top_rounded,
                      color: status.mapAvailable
                          ? SweePiColors.secondary
                          : SweePiColors.accent,
                    ),
                  ],
                ),
                const SizedBox(height: SweePiSpacing.md),
                _InfoLine(label: 'Map name', value: status.mapName ?? 'None'),
                _InfoLine(
                  label: 'Last saved map',
                  value: controller.lastSavedMapId ?? 'None',
                ),
                if (status.progressPercent != null) ...[
                  const SizedBox(height: SweePiSpacing.sm),
                  LinearProgressIndicator(
                    value: (status.progressPercent! / 100).clamp(0.0, 1.0),
                    minHeight: 10,
                    borderRadius: BorderRadius.circular(SweePiRadius.xl),
                  ),
                ],
              ],
            ),
          ),
          if (isManual) ...[
            const SizedBox(height: SweePiSpacing.md),
            SweePiPanel(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader(
                    title: 'Manual Drive',
                    subtitle: 'Hold a direction to move, tap stop to brake.',
                    icon: Icons.gamepad_rounded,
                  ),
                  const SizedBox(height: SweePiSpacing.md),
                  Text(
                    'Speed: ${_speed.toStringAsFixed(2)}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
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
                  const SizedBox(height: SweePiSpacing.sm),
                  Center(
                    child: _RcController(controller: controller, speed: _speed),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _InfoLine extends StatelessWidget {
  const _InfoLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: SweePiSpacing.xs),
      child: Row(
        children: [
          SizedBox(
            width: 112,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
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
                  enabled: enabledFor('left'),
                  active: heldCommand == 'left',
                  onHoldStart: () => _startHolding('left'),
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
                  enabled: enabledFor('right'),
                  active: heldCommand == 'right',
                  onHoldStart: () => _startHolding('right'),
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
