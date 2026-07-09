import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/sweepi_widgets.dart';
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

    return AppBackground(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 104),
        children: [
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'Cleaning Plan',
                  subtitle: metadata == null
                      ? 'Select a map and set a start pose.'
                      : 'Map: ${metadata.name}',
                  icon: Icons.cleaning_services_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
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
                const SizedBox(height: SweePiSpacing.md),
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
                  const SizedBox(height: SweePiSpacing.sm),
                  _SectionMapPicker(
                    controller: controller,
                    message: _sectionMessage,
                    onSectionSelected: () {
                      setState(() => _sectionMessage = null);
                    },
                  ),
                ],
                const SizedBox(height: SweePiSpacing.sm),
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
                const SizedBox(height: SweePiSpacing.md),
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
          const SizedBox(height: SweePiSpacing.md),
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'Current Task',
                  subtitle: taskId == null
                      ? 'No active cleaning task'
                      : 'Task $taskId',
                  icon: Icons.task_alt_rounded,
                  trailing: StatusChip(
                    label: cleaning.state,
                    icon: Icons.circle_rounded,
                    color: statusColorForText(cleaning.state),
                  ),
                ),
                const SizedBox(height: SweePiSpacing.lg),
                Row(
                  children: [
                    SizedBox(
                      width: 92,
                      height: 92,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          CircularProgressIndicator(
                            value: (progressPercent / 100).clamp(0.0, 1.0),
                            strokeWidth: 9,
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.surfaceContainerHighest,
                          ),
                          Center(
                            child: Text(
                              '${progressPercent.toStringAsFixed(0)}%',
                              style: Theme.of(context).textTheme.titleLarge
                                  ?.copyWith(fontWeight: FontWeight.w900),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: SweePiSpacing.lg),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _TaskLine(
                            label: 'Robot state',
                            value: controller.robotStatus.state,
                          ),
                          _TaskLine(label: 'Map ID', value: mapId ?? 'None'),
                          _TaskLine(
                            label: 'Mode',
                            value: cleaningMode ?? 'None',
                          ),
                          _TaskLine(label: 'Navigation', value: navStatus),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: SweePiSpacing.lg),
                Wrap(
                  spacing: SweePiSpacing.sm,
                  runSpacing: SweePiSpacing.sm,
                  children: [
                    StatusChip(
                      label: cleaning.initialPoseConfirmed
                          ? 'Pose confirmed'
                          : cleaning.initialPoseReceived
                          ? 'Pose received'
                          : 'Pose not set',
                      icon: Icons.my_location_rounded,
                      color: cleaning.initialPoseConfirmed
                          ? SweePiColors.secondary
                          : SweePiColors.accent,
                    ),
                    StatusChip(
                      label: cleaning.coverageValidated
                          ? 'Validation complete'
                          : cleaning.readyToValidate
                          ? 'Ready to validate'
                          : 'Validation pending',
                      icon: Icons.fact_check_rounded,
                      color: cleaning.coverageValidated
                          ? SweePiColors.secondary
                          : SweePiColors.primary,
                    ),
                    StatusChip(
                      label: cleaning.readyToStartMotion
                          ? 'Ready to move'
                          : 'Motion pending',
                      icon: Icons.navigation_rounded,
                      color: cleaning.readyToStartMotion
                          ? SweePiColors.secondary
                          : SweePiColors.accent,
                    ),
                  ],
                ),
                const SizedBox(height: SweePiSpacing.md),
                _TaskLine(
                  label: 'Coverage map',
                  value: cleaning.coverageMapId ?? 'None',
                ),
                if (cleaning.taskFinished)
                  _TaskLine(
                    label: 'Task result',
                    value: cleaning.taskResult ?? 'Finished',
                  ),
                if (cleaning.lastError != null)
                  _TaskLine(
                    label: 'Last error',
                    value: cleaning.lastError!,
                    danger: true,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TaskLine extends StatelessWidget {
  const _TaskLine({
    required this.label,
    required this.value,
    this.danger = false,
  });

  final String label;
  final String value;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: SweePiSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 104,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: danger
                    ? colorScheme.error
                    : colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
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
                child: ColorfulActionButton(
                  label: 'Start',
                  icon: Icons.play_arrow_rounded,
                  color: SweePiColors.secondary,
                  onPressed: controller.isBusy || !_hasMap ? null : onStart,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ColorfulActionButton(
                  label: 'Give pos',
                  icon: Icons.my_location_rounded,
                  color: SweePiColors.primary,
                  onPressed: controller.isBusy || !_hasMap || !canGivePose
                      ? null
                      : onGivePose,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ColorfulActionButton(
                  label: 'Validation',
                  icon: Icons.fact_check_rounded,
                  color: SweePiColors.accent,
                  onPressed: controller.isBusy || !_hasMap ? null : onValidate,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ColorfulActionButton(
                  label: 'Start move',
                  icon: Icons.navigation_rounded,
                  color: SweePiColors.primaryDeep,
                  onPressed: controller.isBusy || !_hasMap ? null : onStartMove,
                ),
              ),
            ],
          ),
        ] else ...[
          Row(
            children: [
              Expanded(
                child: ColorfulActionButton(
                  label: isPaused ? 'Continue' : 'Pause',
                  icon: isPaused
                      ? Icons.play_arrow_rounded
                      : Icons.pause_rounded,
                  color: isPaused
                      ? SweePiColors.secondary
                      : SweePiColors.accent,
                  onPressed: controller.isBusy
                      ? null
                      : () {
                          if (isPaused) {
                            controller.resumeCleaning();
                          } else {
                            controller.pauseCleaning();
                          }
                        },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ColorfulActionButton(
                  label: 'Stop',
                  icon: Icons.stop_rounded,
                  color: SweePiColors.danger,
                  onPressed: controller.isBusy ? null : controller.stopCleaning,
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: ColorfulActionButton(
                label: 'Return home',
                icon: Icons.home_rounded,
                color: SweePiColors.primary,
                onPressed: controller.isBusy ? null : controller.returnHome,
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
