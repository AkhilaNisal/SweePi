import 'package:flutter/material.dart';

import '../../core/models/robot_models.dart';
import '../app/app_controller.dart';

class SchedulesScreen extends StatelessWidget {
  const SchedulesScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Schedules',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              FilledButton(
                onPressed: () => _showScheduleDialog(context),
                child: const Text('Add Schedule'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: controller.schedules.isEmpty
                ? const Center(
                    child: Text('No schedules yet. Save a zone, then add one.'),
                  )
                : ListView.separated(
                    itemCount: controller.schedules.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final schedule = controller.schedules[index];
                      return Card(
                        child: ListTile(
                          title: Text('${schedule.timeLocal}  ${schedule.days.join(', ')}'),
                          subtitle: Text(
                            'Zones: ${((schedule.selection['zones'] as List?) ?? const []).length}',
                          ),
                          trailing: IconButton(
                            onPressed: () => controller.deleteSchedule(schedule.id),
                            icon: const Icon(Icons.delete_outline),
                          ),
                          onTap: () => _showScheduleDialog(context, existing: schedule),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Future<void> _showScheduleDialog(
    BuildContext context, {
    ScheduleItem? existing,
  }) async {
    final timeController = TextEditingController(text: existing?.timeLocal ?? '09:00');
    final days = <String>{
      ...?existing?.days,
      if (existing == null) 'MON',
      if (existing == null) 'WED',
      if (existing == null) 'FRI',
    };

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(existing == null ? 'Add Schedule' : 'Edit Schedule'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: timeController,
                    decoration: const InputDecoration(
                      labelText: 'Time (HH:MM)',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    children: [
                      for (final day in const ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'])
                        FilterChip(
                          label: Text(day),
                          selected: days.contains(day),
                          onSelected: (selected) {
                            setState(() {
                              if (selected) {
                                days.add(day);
                              } else {
                                days.remove(day);
                              }
                            });
                          },
                        ),
                    ],
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    controller.saveSchedule(
                      id: existing?.id ??
                          'sch_${DateTime.now().millisecondsSinceEpoch}',
                      timeLocal: timeController.text,
                      days: days.toList()..sort(),
                    );
                    Navigator.of(context).pop();
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );
  }
}
