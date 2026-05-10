import 'package:flutter/material.dart';

import '../app/app_controller.dart';

class ControlScreen extends StatelessWidget {
  const ControlScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final status = controller.status;
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
                  'Robot State',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Text('State: ${status.state}'),
                Text('Execution: ${status.executionStatus}'),
                Text('Progress: ${status.progressPercent.toStringAsFixed(1)}%'),
                if (status.pose != null)
                  Text(
                    'Pose: (${status.pose!.x.toStringAsFixed(2)}, '
                    '${status.pose!.y.toStringAsFixed(2)})',
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton(
              onPressed: controller.isBusy
                  ? null
                  : () => controller.sendCommand('/api/v1/cleaning/start'),
              child: const Text('Start Full Clean'),
            ),
            FilledButton(
              onPressed: controller.isBusy
                  ? null
                  : () => controller.sendCommand('/api/v1/cleaning/pause'),
              child: const Text('Pause'),
            ),
            FilledButton(
              onPressed: controller.isBusy
                  ? null
                  : () => controller.sendCommand('/api/v1/cleaning/resume'),
              child: const Text('Resume'),
            ),
            OutlinedButton(
              onPressed: controller.isBusy
                  ? null
                  : () => controller.sendCommand('/api/v1/cleaning/stop'),
              child: const Text('Stop'),
            ),
            OutlinedButton(
              onPressed: controller.isBusy
                  ? null
                  : () => controller.sendCommand('/api/v1/robot/return-to-dock'),
              child: const Text('Return To Dock'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (controller.errorMessage != null)
          Card(
            color: const Color(0xFFFFF0EE),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text(controller.errorMessage!),
            ),
          ),
        if (status.errors.isNotEmpty || status.warnings.isNotEmpty) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Robot Messages',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  for (final error in status.errors)
                    Text('Error: $error', style: const TextStyle(color: Colors.red)),
                  for (final warning in status.warnings)
                    Text('Warning: $warning'),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Cleaning History',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                if (controller.history.isEmpty)
                  const Text('No cleaning runs recorded yet.')
                else
                  for (final item in controller.history.take(5))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Text(
                        '${item.taskType} - ${item.result ?? 'running'} - '
                        '${item.coveragePercent?.toStringAsFixed(1) ?? '--'}%',
                      ),
                    ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
