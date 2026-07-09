import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/sweepi_widgets.dart';
import '../app/app_controller.dart';
import 'map_canvas.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  bool _deleteMode = false;

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final metadata = controller.selectedMapMetadata;
    final mapData = controller.selectedMapData ?? SweePiMapData.empty;
    final selection = controller.pendingSelection;

    return AppBackground(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 104),
        children: [
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'Saved Maps',
                  subtitle: 'Open a map, draw sections, then save metadata.',
                  icon: Icons.map_rounded,
                  trailing: IconButton.filledTonal(
                    tooltip: 'Refresh maps',
                    onPressed: controller.isBusy
                        ? null
                        : controller.refreshMaps,
                    icon: controller.isBusy
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh_rounded),
                  ),
                ),
                const SizedBox(height: SweePiSpacing.md),
                if (controller.savedMaps.isEmpty)
                  const EmptyState(
                    icon: Icons.map_outlined,
                    title: 'No maps saved yet',
                    message:
                        'Run exploration and save a map before creating cleaning sections.',
                  )
                else
                  SizedBox(
                    height: 182,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: controller.savedMaps.length,
                      separatorBuilder: (_, _) =>
                          const SizedBox(width: SweePiSpacing.md),
                      itemBuilder: (context, index) {
                        final map = controller.savedMaps[index];
                        return SizedBox(
                          width: 300,
                          child: ColorfulMapCard(
                            map: map,
                            selected: metadata?.mapId == map.mapId,
                            onSelected: controller.isBusy
                                ? null
                                : () => controller.selectMap(map.mapId),
                          ),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: SweePiSpacing.md),
          SweePiPanel(
            padding: const EdgeInsets.all(SweePiSpacing.md),
            child: SizedBox(
              height: 360,
              child: mapData.available
                  ? MapCanvas(
                      mapData: mapData,
                      selection: selection,
                      robotPose: controller.robotStatus.pose,
                      sections: metadata?.sections ?? const [],
                      onSelectionChanged: _deleteMode
                          ? (_) {}
                          : controller.setPendingSelection,
                      selectionEnabled: !_deleteMode,
                      onSectionTap: _deleteMode
                          ? (section) {
                              if (section != null) {
                                controller.deleteSection(section);
                                setState(() => _deleteMode = false);
                              }
                            }
                          : null,
                    )
                  : const EmptyState(
                      icon: Icons.travel_explore_rounded,
                      title: 'Select a map',
                      message:
                          'Occupancy data and saved sections will appear here.',
                    ),
            ),
          ),
          const SizedBox(height: SweePiSpacing.md),
          SweePiPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  title: 'Section Tools',
                  subtitle:
                      'Drag on the map to create or manage cleaning zones.',
                  icon: Icons.dashboard_customize_rounded,
                ),
                const SizedBox(height: SweePiSpacing.md),
                Wrap(
                  spacing: SweePiSpacing.md,
                  runSpacing: SweePiSpacing.md,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    FilledButton.icon(
                      onPressed:
                          selection == null ||
                              metadata == null ||
                              controller.isBusy
                          ? null
                          : () => _addSection(context, mapData, selection),
                      icon: const Icon(Icons.add_rounded),
                      label: const Text('Add Section'),
                    ),
                    FilledButton.icon(
                      onPressed: metadata == null || controller.isBusy
                          ? null
                          : controller.saveSelectedMapMetadata,
                      icon: const Icon(Icons.save_outlined),
                      label: const Text('Save Metadata'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => controller.setPendingSelection(null),
                      icon: const Icon(Icons.clear_rounded),
                      label: const Text('Clear Selection'),
                    ),
                    OutlinedButton.icon(
                      onPressed:
                          metadata == null ||
                              metadata.sections.isEmpty ||
                              controller.isBusy
                          ? null
                          : () {
                              controller.setPendingSelection(null);
                              setState(() => _deleteMode = true);
                            },
                      icon: const Icon(Icons.delete_outline_rounded),
                      label: const Text('Delete Section'),
                    ),
                  ],
                ),
                if (_deleteMode) ...[
                  const SizedBox(height: SweePiSpacing.md),
                  MaterialBanner(
                    padding: EdgeInsets.zero,
                    leading: const Icon(Icons.touch_app_rounded),
                    content: const Text('Tap a section to delete it.'),
                    actions: [
                      TextButton(
                        onPressed: () => setState(() => _deleteMode = false),
                        child: const Text('Cancel'),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: SweePiSpacing.md),
          _MetadataAndSections(controller: controller),
        ],
      ),
    );
  }

  Future<void> _addSection(
    BuildContext context,
    SweePiMapData mapData,
    RectSelection selection,
  ) async {
    debugPrint('[MapScreen] Add Section dialog opening.');
    final sectionName = await showDialog<String>(
      context: context,
      builder: (dialogContext) => const _SectionNameDialog(),
    );
    debugPrint('[MapScreen] Add Section dialog closed: "$sectionName".');

    try {
      if (!mounted || sectionName == null) {
        widget.controller.setPendingSelection(null);
        debugPrint('[MapScreen] Add Section cancelled; selection cleared.');
        return;
      }
      await widget.controller.addSectionFromBounds(
        sectionName,
        selection.toWorldBounds(mapData),
      );
      widget.controller.setPendingSelection(null);
      debugPrint('[MapScreen] Added section "$sectionName".');
    } catch (error, stackTrace) {
      debugPrint('[MapScreen] Failed to add section: $error');
      debugPrintStack(stackTrace: stackTrace);
      widget.controller.setPendingSelection(null);
      rethrow;
    }
  }
}

class _SectionNameDialog extends StatefulWidget {
  const _SectionNameDialog();

  @override
  State<_SectionNameDialog> createState() => _SectionNameDialogState();
}

class _SectionNameDialogState extends State<_SectionNameDialog> {
  late final TextEditingController _nameController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Name section'),
      content: TextField(
        controller: _nameController,
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Section name'),
        onSubmitted: (value) {
          debugPrint('[MapScreen] Add Section submitted from keyboard.');
          Navigator.of(context).pop(value);
        },
      ),
      actions: [
        TextButton(
          onPressed: () {
            debugPrint('[MapScreen] Add Section cancelled from dialog.');
            Navigator.of(context).pop();
          },
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            debugPrint('[MapScreen] Add Section confirmed from dialog.');
            Navigator.of(context).pop(_nameController.text);
          },
          child: const Text('Add'),
        ),
      ],
    );
  }
}

class _MetadataAndSections extends StatelessWidget {
  const _MetadataAndSections({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final metadata = controller.selectedMapMetadata;
    if (metadata == null) {
      return const SweePiPanel(
        child: EmptyState(
          icon: Icons.info_outline_rounded,
          title: 'No map selected',
          message: 'Choose a saved map to see its details and sections.',
        ),
      );
    }

    return SweePiPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: metadata.name,
            subtitle: metadata.mapId,
            icon: Icons.layers_rounded,
          ),
          const SizedBox(height: SweePiSpacing.md),
          Wrap(
            spacing: SweePiSpacing.sm,
            runSpacing: SweePiSpacing.sm,
            children: [
              StatusChip(
                label: '${metadata.sections.length} sections',
                icon: Icons.dashboard_rounded,
                color: SweePiColors.primary,
              ),
              StatusChip(
                label: '${metadata.width ?? '--'} x ${metadata.height ?? '--'}',
                icon: Icons.aspect_ratio_rounded,
                color: SweePiColors.secondary,
              ),
              StatusChip(
                label: 'Resolution ${metadata.resolution}',
                icon: Icons.straighten_rounded,
                color: SweePiColors.accent,
              ),
            ],
          ),
          const SizedBox(height: SweePiSpacing.md),
          Text(
            'Updated: ${metadata.updatedAt.isEmpty ? '--' : metadata.updatedAt}',
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const Divider(height: 28),
          if (metadata.sections.isEmpty)
            const EmptyState(
              icon: Icons.crop_square_rounded,
              title: 'No sections saved',
              message: 'Drag on the map, add a section, then save metadata.',
            )
          else
            for (final section in metadata.sections)
              CheckboxListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                value: controller.selectedSections.any(
                  (item) => item.sectionId == section.sectionId,
                ),
                onChanged: (_) {
                  controller.toggleSectionForCleaning(section);
                },
                title: Text(section.name),
                subtitle: Text(section.sectionId),
                secondary: const Icon(Icons.crop_free_rounded),
              ),
        ],
      ),
    );
  }
}
