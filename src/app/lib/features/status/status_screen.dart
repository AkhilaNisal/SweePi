import 'package:flutter/material.dart';

import '../app/app_controller.dart';

class StatusScreen extends StatelessWidget {
  const StatusScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final status = controller.robotStatus;
    final pose = status.pose;

    return RefreshIndicator(
      onRefresh: controller.refreshRobotStatus,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _MessagePanel(controller: controller),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Robot Status',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Refresh status',
                        onPressed: controller.isBusy
                            ? null
                            : controller.refreshRobotStatus,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _StatusRow(label: 'Robot ID', value: status.robotId),
                  _StatusRow(label: 'State', value: status.state),
                  _StatusRow(label: 'Mode', value: status.mode),
                  _StatusRow(
                    label: 'Battery',
                    value:
                        '${status.battery.percent}% ${status.battery.charging ? '(charging)' : '(not charging)'}',
                  ),
                  _StatusRow(
                    label: 'Active map',
                    value: status.map.mapId ?? 'None',
                  ),
                  _StatusRow(
                    label: 'Cleaning task',
                    value: status.cleaning.taskId ?? 'None',
                  ),
                  _StatusRow(
                    label: 'Cleaning map',
                    value: status.cleaning.mapId ?? 'None',
                  ),
                  _StatusRow(
                    label: 'Progress',
                    value:
                        '${status.cleaning.progressPercent.toStringAsFixed(1)}%',
                  ),
                  _StatusRow(
                    label: 'Navigation',
                    value: status.nav.executionStatus,
                  ),
                  if (pose != null) ...[
                    const Divider(height: 24),
                    _StatusRow(
                      label: 'Pose',
                      value:
                          'x ${pose.x.toStringAsFixed(2)}, y ${pose.y.toStringAsFixed(2)}, yaw ${pose.yaw.toStringAsFixed(2)}',
                    ),
                    _StatusRow(label: 'Frame', value: pose.frame),
                  ],
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
                    'Messages',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  if (status.errors.isEmpty && status.warnings.isEmpty)
                    const Text('No robot errors or warnings.')
                  else ...[
                    for (final error in status.errors)
                      Text(
                        'Error: $error',
                        style: const TextStyle(color: Colors.red),
                      ),
                    for (final warning in status.warnings)
                      Text('Warning: $warning'),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(child: Text(value)),
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

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        color: error != null ? const Color(0xFFFFF0EE) : null,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            controller.isBusy ? 'Working...' : error ?? message ?? '',
          ),
        ),
      ),
    );
  }
}
