import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../app/app_controller.dart';
import '../map/map_canvas.dart';

class CleaningScreen extends StatefulWidget {
  const CleaningScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<CleaningScreen> createState() => _CleaningScreenState();
}

class _CleaningScreenState extends State<CleaningScreen> {
  bool _fullMap = true;
  String? _sectionMessage;

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final metadata = controller.selectedMapMetadata;
    final cleaning = controller.robotStatus.cleaning;
    final isCleaningActive = controller.isCleaningActive;
    final isPaused = controller.isCleaningPaused;

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
                  initialValue: metadata?.mapId,
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
                  subtitle: const Text('Turn off to clean one saved section.'),
                  value: _fullMap,
                  onChanged: (value) {
                    setState(() {
                      _fullMap = value;
                      _sectionMessage = null;
                    });
                  },
                ),
                if (!_fullMap) ...[
                  const SizedBox(height: 8),
                  _SectionMapPicker(
                    controller: controller,
                    message: _sectionMessage,
                    onSectionSelected: () {
                      setState(() => _sectionMessage = null);
                    },
                  ),
                ] else ...[
                  const SizedBox(height: 8),
                  _InitialPosePicker(
                    controller: controller,
                    mapData: controller.selectedMapData ?? SweePiMapData.empty,
                  ),
                ],
                const SizedBox(height: 12),
                _CleaningActions(
                  controller: controller,
                  metadata: metadata,
                  isCleaningActive: isCleaningActive,
                  isPaused: isPaused,
                  onStart: () {
                    if (!_fullMap && controller.selectedSections.isEmpty) {
                      setState(() {
                        _sectionMessage = 'Select a section before starting.';
                      });
                      return;
                    }
                    controller.startCleaning(fullMap: _fullMap);
                  },
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
                Text(
                  'Navigation: ${controller.robotStatus.nav.executionStatus}',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _CleaningActions extends StatelessWidget {
  const _CleaningActions({
    required this.controller,
    required this.metadata,
    required this.isCleaningActive,
    required this.isPaused,
    required this.onStart,
  });

  final AppController controller;
  final SweePiMapMetadata? metadata;
  final bool isCleaningActive;
  final bool isPaused;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (!isCleaningActive)
          Expanded(
            child: SizedBox(
              height: 52,
              child: FilledButton.icon(
                onPressed: controller.isBusy || metadata == null
                    ? null
                    : onStart,
                icon: const Icon(Icons.play_arrow_rounded, size: 22),
                label: const Text('Start'),
              ),
            ),
          )
        else ...[
          Expanded(
            child: SizedBox(
              height: 52,
              child: FilledButton.tonal(
                onPressed: controller.isBusy
                    ? null
                    : () {
                        if (isPaused) {
                          controller.resumeCleaning();
                        } else {
                          controller.pauseCleaning();
                        }
                      },
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        isPaused
                            ? Icons.play_arrow_rounded
                            : Icons.pause_rounded,
                        size: 21,
                      ),
                      const SizedBox(width: 6),
                      Text(isPaused ? 'Resume' : 'Pause'),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: SizedBox(
              height: 52,
              child: FilledButton.icon(
                onPressed: controller.isBusy ? null : controller.stopCleaning,
                icon: const Icon(Icons.stop_rounded, size: 22),
                label: const FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text('Stop'),
                ),
              ),
            ),
          ),
        ],
        const SizedBox(width: 8),
        SizedBox(
          width: 52,
          height: 52,
          child: IconButton.filledTonal(
            tooltip: 'Refresh state',
            onPressed: controller.isBusy ? null : controller.refreshRobotStatus,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ),
      ],
    );
  }
}

class _SectionMapPicker extends StatelessWidget {
  const _SectionMapPicker({
    required this.controller,
    required this.message,
    required this.onSectionSelected,
  });

  final AppController controller;
  final String? message;
  final VoidCallback onSectionSelected;

  @override
  Widget build(BuildContext context) {
    final metadata = controller.selectedMapMetadata;
    final mapData = controller.selectedMapData ?? SweePiMapData.empty;
    final sections = metadata?.sections ?? const <MapSection>[];
    final selectedSection = controller.selectedSections.isEmpty
        ? null
        : controller.selectedSections.first;
    final colorScheme = Theme.of(context).colorScheme;

    if (metadata == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text('Select a map before choosing sections.'),
      );
    }

    if (sections.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text('No sections saved for this map yet.'),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 280,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: colorScheme.surface,
              border: Border.all(color: colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: MapCanvas(
                mapData: mapData,
                selection: null,
                onSelectionChanged: (_) {},
                robotPose: controller.robotStatus.pose,
                sections: sections,
                selectedSectionIds: {
                  if (selectedSection != null) selectedSection.sectionId,
                },
                selectionEnabled: false,
                onSectionTap: (section) {
                  controller.selectSectionForCleaning(section);
                  if (section != null) {
                    onSectionSelected();
                  }
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final section in sections)
              ChoiceChip(
                label: Text(section.name),
                selected: selectedSection?.sectionId == section.sectionId,
                onSelected: (_) {
                  controller.selectSectionForCleaning(section);
                  onSectionSelected();
                },
              ),
          ],
        ),
        const SizedBox(height: 8),
        if (selectedSection == null)
          Text(
            message ?? 'Tap a saved section on the map to clean it.',
            style: TextStyle(
              color: message == null
                  ? colorScheme.onSurfaceVariant
                  : colorScheme.error,
              fontWeight: message == null ? null : FontWeight.w600,
            ),
          )
        else
          Text(
            'Selected section: ${selectedSection.name}',
            style: TextStyle(
              color: colorScheme.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
        if (selectedSection != null) ...[
          const SizedBox(height: 12),
          _ProcessedSectionPreview(controller: controller),
        ],
      ],
    );
  }
}

class _ProcessedSectionPreview extends StatelessWidget {
  const _ProcessedSectionPreview({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final previewMap = controller.processedSectionMapPreview;
    final colorScheme = Theme.of(context).colorScheme;

    if (previewMap == null) {
      return Text(
        'Processed map preview is not available.',
        style: TextStyle(color: colorScheme.error),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Processed map preview',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            const Text('Boundary'),
            Expanded(
              child: Slider(
                min: 1,
                max: 24,
                divisions: 23,
                label: '${controller.sectionBoundaryThicknessCells} cells',
                value: controller.sectionBoundaryThicknessCells.toDouble(),
                onChanged: controller.isBusy
                    ? null
                    : (value) {
                        controller.setSectionBoundaryThicknessCells(
                          value.round(),
                        );
                      },
              ),
            ),
            SizedBox(
              width: 64,
              child: Text('${controller.sectionBoundaryThicknessCells} cells'),
            ),
          ],
        ),
        SizedBox(
          height: 280,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: colorScheme.surface,
              border: Border.all(color: colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: MapCanvas(
                mapData: previewMap,
                selection: null,
                onSelectionChanged: (_) {},
                robotPose: controller.robotStatus.pose,
                plannedInitialPose: controller.plannedInitialPose,
                onInitialPoseChanged: controller.setPlannedInitialPose,
                initialPoseEnabled: !controller.isBusy,
                selectionEnabled: false,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        _InitialPoseSummary(controller: controller),
      ],
    );
  }
}

class _InitialPosePicker extends StatelessWidget {
  const _InitialPosePicker({required this.controller, required this.mapData});

  final AppController controller;
  final SweePiMapData mapData;

  @override
  Widget build(BuildContext context) {
    if (!mapData.available) {
      return const SizedBox.shrink();
    }

    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Start pose', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        SizedBox(
          height: 240,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: colorScheme.surface,
              border: Border.all(color: colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: MapCanvas(
                mapData: mapData,
                selection: null,
                onSelectionChanged: (_) {},
                robotPose: controller.robotStatus.pose,
                plannedInitialPose: controller.plannedInitialPose,
                onInitialPoseChanged: controller.setPlannedInitialPose,
                initialPoseEnabled: !controller.isBusy,
                selectionEnabled: false,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        _InitialPoseSummary(controller: controller),
      ],
    );
  }
}

class _InitialPoseSummary extends StatelessWidget {
  const _InitialPoseSummary({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final pose = controller.plannedInitialPose;
    final colorScheme = Theme.of(context).colorScheme;

    return Row(
      children: [
        Expanded(
          child: Text(
            pose == null
                ? 'No start pose set.'
                : 'Start: ${pose.x.toStringAsFixed(2)}, '
                      '${pose.y.toStringAsFixed(2)}, '
                      '${pose.yaw.toStringAsFixed(2)} rad',
            style: TextStyle(color: colorScheme.onSurfaceVariant),
          ),
        ),
        TextButton.icon(
          onPressed: pose == null || controller.isBusy
              ? null
              : () => controller.setPlannedInitialPose(null),
          icon: const Icon(Icons.clear_rounded),
          label: const Text('Clear'),
        ),
      ],
    );
  }
}
