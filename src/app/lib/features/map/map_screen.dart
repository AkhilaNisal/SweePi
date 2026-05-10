import 'package:flutter/material.dart';

import '../app/app_controller.dart';
import 'map_canvas.dart';

class MapScreen extends StatelessWidget {
  const MapScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final selection = controller.pendingSelection;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Cleaning Map',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Drag on the map to define a rectangular cleaning zone, then save it '
            'for selected-area cleaning or schedules.',
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Card(
              clipBehavior: Clip.antiAlias,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: MapCanvas(
                  mapPayload: controller.mapPayload,
                  selection: selection,
                  onSelectionChanged: controller.setPendingSelection,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton(
                onPressed: selection == null || controller.isBusy
                    ? null
                    : controller.saveSelection,
                child: const Text('Save Selected Area'),
              ),
              FilledButton.tonal(
                onPressed: controller.isBusy
                    ? null
                    : controller.startSelectedCleaning,
                child: const Text('Start Selected Clean'),
              ),
              OutlinedButton(
                onPressed: () => controller.setPendingSelection(null),
                child: const Text('Clear Selection'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
