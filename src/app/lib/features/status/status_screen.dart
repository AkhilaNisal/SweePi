import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../core/widgets/sweepi_widgets.dart';
import '../app/app_controller.dart';

class StatusScreen extends StatelessWidget {
  const StatusScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final status = controller.robotStatus;
    final pose = status.pose;
    final stateColor = statusColorForText(
      status.state,
      connected: controller.isConnected,
    );
    final navColor = statusColorForText(
      status.nav.executionStatus,
      connected: controller.isConnected,
    );

    return AppBackground(
      child: RefreshIndicator(
        onRefresh: controller.refreshRobotStatus,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 104),
          children: [
            _MessagePanel(controller: controller),
            SweePiPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionHeader(
                    title: 'Robot Dashboard',
                    subtitle: 'Live state, battery, navigation, and pose',
                    icon: Icons.smart_toy_rounded,
                    trailing: IconButton.filledTonal(
                      tooltip: 'Refresh status',
                      onPressed: controller.isBusy
                          ? null
                          : controller.refreshRobotStatus,
                      icon: const Icon(Icons.refresh_rounded),
                    ),
                  ),
                  const SizedBox(height: SweePiSpacing.md),
                  Wrap(
                    spacing: SweePiSpacing.sm,
                    runSpacing: SweePiSpacing.sm,
                    children: [
                      StatusChip(
                        label: status.state,
                        icon: Icons.bolt_rounded,
                        color: stateColor,
                      ),
                      StatusChip(
                        label: status.mode,
                        icon: Icons.tune_rounded,
                        color: SweePiColors.primary,
                      ),
                      StatusChip(
                        label: status.nav.executionStatus,
                        icon: Icons.route_rounded,
                        color: navColor,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: SweePiSpacing.md),
            _MetricGrid(
              children: [
                MetricCard(
                  title: 'Robot state',
                  value: status.state,
                  subtitle: status.robotId,
                  icon: Icons.memory_rounded,
                  color: stateColor,
                ),
                RobotBatteryCard(
                  percent: status.battery.percent,
                  charging: status.battery.charging,
                ),
                MetricCard(
                  title: 'Current mode',
                  value: status.mode,
                  subtitle: 'Map: ${status.map.mapId ?? 'None'}',
                  icon: Icons.auto_mode_rounded,
                  color: SweePiColors.primary,
                ),
                MetricCard(
                  title: 'Cleaning',
                  value:
                      '${status.cleaning.progressPercent.toStringAsFixed(1)}%',
                  subtitle: status.cleaning.taskId ?? 'No active task',
                  icon: Icons.cleaning_services_rounded,
                  color: SweePiColors.accent,
                  child: LinearProgressIndicator(
                    value: (status.cleaning.progressPercent / 100).clamp(
                      0.0,
                      1.0,
                    ),
                    minHeight: 10,
                    borderRadius: BorderRadius.circular(SweePiRadius.xl),
                  ),
                ),
              ],
            ),
            const SizedBox(height: SweePiSpacing.md),
            SweePiPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader(
                    title: 'Location',
                    subtitle: 'Current pose and connection details',
                    icon: Icons.my_location_rounded,
                  ),
                  const SizedBox(height: SweePiSpacing.md),
                  _StatusRow(label: 'Active map', value: status.map.mapId),
                  _StatusRow(
                    label: 'Cleaning map',
                    value: status.cleaning.mapId,
                  ),
                  _StatusRow(
                    label: 'Connection',
                    value: controller.isConnected ? 'Online' : 'Offline',
                  ),
                  if (pose != null) ...[
                    const Divider(height: 24),
                    _StatusRow(
                      label: 'Pose',
                      value:
                          'x ${pose.x.toStringAsFixed(2)}, y ${pose.y.toStringAsFixed(2)}, yaw ${pose.yaw.toStringAsFixed(2)}',
                    ),
                    _StatusRow(label: 'Frame', value: pose.frame),
                  ] else
                    const Padding(
                      padding: EdgeInsets.only(top: SweePiSpacing.sm),
                      child: EmptyState(
                        icon: Icons.location_off_rounded,
                        title: 'No pose yet',
                        message:
                            'SweePi will show its position here once localization is available.',
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
                  const SectionHeader(
                    title: 'Messages',
                    subtitle: 'Warnings and robot-reported issues',
                    icon: Icons.notifications_active_rounded,
                  ),
                  const SizedBox(height: SweePiSpacing.md),
                  if (status.errors.isEmpty && status.warnings.isEmpty)
                    const StatusChip(
                      label: 'No errors or warnings',
                      icon: Icons.check_circle_rounded,
                      color: SweePiColors.secondary,
                    )
                  else ...[
                    for (final error in status.errors)
                      _AlertLine(
                        icon: Icons.error_rounded,
                        text: error,
                        color: Theme.of(context).colorScheme.error,
                      ),
                    for (final warning in status.warnings)
                      _AlertLine(
                        icon: Icons.warning_rounded,
                        text: warning,
                        color: SweePiColors.accent,
                      ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 640 ? 4 : 2;
        final width =
            (constraints.maxWidth - (columns - 1) * SweePiSpacing.md) / columns;
        return Wrap(
          spacing: SweePiSpacing.md,
          runSpacing: SweePiSpacing.md,
          children: [
            for (final child in children) SizedBox(width: width, child: child),
          ],
        );
      },
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({required this.label, required this.value});

  final String label;
  final String? value;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 118,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Expanded(
            child: Text(
              value?.isNotEmpty == true ? value! : 'None',
              style: TextStyle(color: colorScheme.onSurfaceVariant),
            ),
          ),
        ],
      ),
    );
  }
}

class _AlertLine extends StatelessWidget {
  const _AlertLine({
    required this.icon,
    required this.text,
    required this.color,
  });

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: SweePiSpacing.sm),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: SweePiSpacing.sm),
          Expanded(
            child: Text(text, style: TextStyle(color: color)),
          ),
        ],
      ),
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final error = controller.errorMessage;
    final message = controller.lastMessage;
    if (error == null && message == null && !controller.isBusy) {
      return const SizedBox.shrink();
    }

    final color = error != null
        ? Theme.of(context).colorScheme.error
        : SweePiColors.primary;

    return Padding(
      padding: const EdgeInsets.only(bottom: SweePiSpacing.md),
      child: SweePiPanel(
        child: Row(
          children: [
            if (controller.isBusy)
              SizedBox.square(
                dimension: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: color,
                ),
              )
            else
              Icon(
                error != null ? Icons.error_rounded : Icons.info,
                color: color,
              ),
            const SizedBox(width: SweePiSpacing.md),
            Expanded(
              child: Text(
                controller.isBusy ? 'Working...' : error ?? message ?? '',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
