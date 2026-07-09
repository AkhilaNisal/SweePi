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

  bool _validateSectionSelection() {
    if (!_fullMap && widget.controller.selectedSections.isEmpty) {
      setState(() {
        _sectionMessage = 'Select at least one section before starting.';
      });
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final metadata = controller.selectedMapMetadata;
    final cleaning = controller.cleaningStatus;
    final robotCleaning = controller.robotStatus.cleaning;
    final taskId = cleaning.taskId ?? robotCleaning.taskId;
    final mapId = cleaning.mapId ?? robotCleaning.mapId;
    final progressPercent = taskId == null
        ? robotCleaning.progressPercent
        : cleaning.progressPercent;
    final cleaningMode = cleaning.cleaningMode ?? robotCleaning.cleaningMode;
    final navStatus = cleaning.navExecutionStatus == 'IDLE'
        ? controller.robotStatus.nav.executionStatus
        : cleaning.navExecutionStatus;
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
                  subtitle: const Text(
                    'Turn off to clean selected saved sections.',
                  ),
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
                ],
                const SizedBox(height: 8),
                _InitialPosePicker(
                  controller: controller,
                  mapData: controller.selectedMapData ?? SweePiMapData.empty,
                  sections: !_fullMap
                      ? controller.selectedSections
                      : const <MapSection>[],
                  selectedSectionIds: !_fullMap
                      ? controller.selectedSections
                            .map((section) => section.sectionId)
                            .toSet()
                      : const <String>{},
                  onSectionTap: !_fullMap
                      ? (section) {
                          controller.toggleSectionForCleaning(section);
                          setState(() => _sectionMessage = null);
                        }
                      : null,
                ),
                const SizedBox(height: 12),
                _CleaningActions(
                  controller: controller,
                  metadata: metadata,
                  isCleaningActive: isCleaningActive,
                  isPaused: isPaused,
                  canGivePose: controller.plannedInitialPose != null,
                  onStart: () {
                    if (_validateSectionSelection()) {
                      controller.cleaning1(fullMap: _fullMap);
                    }
                  },
                  onGivePose: controller.cleaning2,
                  onValidate: controller.cleaning3,
                  onStartMove: controller.cleaning4,
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
                Text('Cleaning state: ${cleaning.state}'),
                Text('Task ID: ${taskId ?? 'None'}'),
                Text('Map ID: ${mapId ?? 'None'}'),
                Text('Coverage map: ${cleaning.coverageMapId ?? 'None'}'),
                Text('Progress: ${progressPercent.toStringAsFixed(1)}%'),
                Text('Mode: ${cleaningMode ?? 'None'}'),
                Text('Navigation: $navStatus'),
                Text(
                  'Initial pose: ${cleaning.initialPoseConfirmed
                      ? 'Confirmed'
                      : cleaning.initialPoseReceived
                      ? 'Received'
                      : 'Not set'}',
                ),
                Text(
                  'Validation: ${cleaning.coverageValidated
                      ? 'Complete'
                      : cleaning.readyToValidate
                      ? 'Ready'
                      : 'Pending'}',
                ),
                Text(
                  'Ready to move: ${cleaning.readyToStartMotion ? 'Yes' : 'No'}',
                ),
                if (cleaning.taskFinished)
                  Text('Task result: ${cleaning.taskResult ?? 'Finished'}'),
                if (cleaning.lastError != null)
                  Text('Last error: ${cleaning.lastError}'),
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
    required this.canGivePose,
    required this.onStart,
    required this.onGivePose,
    required this.onValidate,
    required this.onStartMove,
  });

  final AppController controller;
  final SweePiMapMetadata? metadata;
  final bool isCleaningActive;
  final bool isPaused;
  final bool canGivePose;
  final VoidCallback onStart;
  final VoidCallback onGivePose;
  final VoidCallback onValidate;
  final VoidCallback onStartMove;

  bool get _hasMap => metadata != null;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!isCleaningActive) ...[
          Row(
            children: [
              Expanded(
                child: _CleaningStepButton(
                  label: 'Start',
                  icon: Icons.play_arrow_rounded,
                  onPressed: controller.isBusy || !_hasMap ? null : onStart,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _CleaningStepButton(
                  label: 'Give pos',
                  icon: Icons.my_location_rounded,
                  onPressed: controller.isBusy || !_hasMap || !canGivePose
                      ? null
                      : onGivePose,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _CleaningStepButton(
                  label: 'Validation',
                  icon: Icons.fact_check_rounded,
                  onPressed: controller.isBusy || !_hasMap ? null : onValidate,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _CleaningStepButton(
                  label: 'Start move',
                  icon: Icons.navigation_rounded,
                  onPressed: controller.isBusy || !_hasMap ? null : onStartMove,
                ),
              ),
            ],
          ),
        ] else ...[
          Row(
            children: [
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
              SizedBox(
                height: 52,
                child: FilledButton.icon(
                  onPressed: controller.isBusy ? null : controller.stopCleaning,
                  icon: const Icon(Icons.stop_rounded, size: 22),
                  label: const Text('Stop'),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: SizedBox(
                height: 52,
                child: FilledButton.tonal(
                  onPressed: controller.isBusy ? null : controller.returnHome,
                  child: const FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.home_rounded, size: 22),
                        SizedBox(width: 6),
                        Text('Return home'),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 52,
              height: 52,
              child: IconButton.filledTonal(
                tooltip: 'Reset cleaning',
                onPressed: controller.isBusy ? null : controller.resetCleaning,
                icon: const Icon(Icons.restart_alt_rounded),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 52,
              height: 52,
              child: IconButton.filledTonal(
                tooltip: 'Refresh state',
                onPressed: controller.isBusy
                    ? null
                    : controller.refreshCleaningStatus,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _CleaningStepButton extends StatelessWidget {
  const _CleaningStepButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      width: double.infinity,
      child: FilledButton(
        onPressed: onPressed,
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20),
              const SizedBox(width: 5),
              Text(label),
            ],
          ),
        ),
      ),
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
    final sections = metadata?.sections ?? const <MapSection>[];
    final selectedSectionIds = controller.selectedSections
        .map((section) => section.sectionId)
        .toSet();
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
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final section in sections)
              ChoiceChip(
                label: Text(section.name),
                selected: selectedSectionIds.contains(section.sectionId),
                onSelected: (_) {
                  controller.toggleSectionForCleaning(section);
                  onSectionSelected();
                },
              ),
          ],
        ),
        const SizedBox(height: 8),
        if (controller.selectedSections.isEmpty)
          Text(
            message ?? 'Choose one or more saved sections to clean.',
            style: TextStyle(
              color: message == null
                  ? colorScheme.onSurfaceVariant
                  : colorScheme.error,
              fontWeight: message == null ? null : FontWeight.w600,
            ),
          )
        else
          Text(
            'Selected sections: ${controller.selectedSections.map((section) => section.name).join(', ')}',
            style: TextStyle(
              color: colorScheme.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
      ],
    );
  }
}

class _InitialPosePicker extends StatelessWidget {
  const _InitialPosePicker({
    required this.controller,
    required this.mapData,
    required this.sections,
    required this.selectedSectionIds,
    required this.onSectionTap,
  });

  final AppController controller;
  final SweePiMapData mapData;
  final List<MapSection> sections;
  final Set<String> selectedSectionIds;
  final ValueChanged<MapSection>? onSectionTap;

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
                sections: sections,
                selectedSectionIds: selectedSectionIds,
                onSectionTap: onSectionTap == null
                    ? null
                    : (section) {
                        if (section != null) {
                          onSectionTap!(section);
                        }
                      },
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
