import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../app/app_controller.dart';

class CleaningScreen extends StatefulWidget {
  const CleaningScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<CleaningScreen> createState() => _CleaningScreenState();
}

class _CleaningScreenState extends State<CleaningScreen> {
  bool _fullMap = true;

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final metadata = controller.selectedMapMetadata;
    final cleaning = controller.robotStatus.cleaning;

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
                  'Cleaning',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: metadata?.mapId,
                  decoration: const InputDecoration(
                    labelText: 'Map',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final map in controller.savedMaps)
                      DropdownMenuItem(
                        value: map.mapId,
                        child: Text('${map.name} (${map.mapId})'),
                      ),
                  ],
                  onChanged: controller.isBusy
                      ? null
                      : (mapId) {
                          if (mapId != null) {
                            controller.selectMap(mapId);
                          }
                        },
                ),
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Clean full map'),
                  subtitle: const Text('Turn off to clean selected sections.'),
                  value: _fullMap,
                  onChanged: (value) => setState(() => _fullMap = value),
                ),
                if (!_fullMap) _SectionChecklist(controller: controller),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    FilledButton.icon(
                      onPressed: controller.isBusy || metadata == null
                          ? null
                          : () => controller.startCleaning(fullMap: _fullMap),
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('Start Cleaning'),
                    ),
                    OutlinedButton.icon(
                      onPressed:
                          controller.isBusy ? null : controller.pauseCleaning,
                      icon: const Icon(Icons.pause),
                      label: const Text('Pause'),
                    ),
                    OutlinedButton.icon(
                      onPressed:
                          controller.isBusy ? null : controller.resumeCleaning,
                      icon: const Icon(Icons.play_circle_outline),
                      label: const Text('Resume'),
                    ),
                    OutlinedButton.icon(
                      onPressed:
                          controller.isBusy ? null : controller.stopCleaning,
                      icon: const Icon(Icons.stop),
                      label: const Text('Stop'),
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
                  'Current Task',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text('Robot state: ${controller.robotStatus.state}'),
                Text('Task ID: ${cleaning.taskId ?? 'None'}'),
                Text('Map ID: ${cleaning.mapId ?? 'None'}'),
                Text(
                  'Progress: ${cleaning.progressPercent.toStringAsFixed(1)}%',
                ),
                Text('Navigation: ${controller.robotStatus.nav.executionStatus}'),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _SectionChecklist extends StatelessWidget {
  const _SectionChecklist({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final sections = controller.selectedMapMetadata?.sections ?? const <MapSection>[];
    if (sections.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text('No sections saved for this map yet.'),
      );
    }

    return Column(
      children: [
        for (final section in sections)
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: controller.selectedSections.any(
              (item) => item.sectionId == section.sectionId,
            ),
            onChanged: (_) => controller.toggleSectionForCleaning(section),
            title: Text(section.name),
            subtitle: Text(section.sectionId),
          ),
      ],
    );
  }
}
