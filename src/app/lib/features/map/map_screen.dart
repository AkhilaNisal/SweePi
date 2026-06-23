import 'package:flutter/material.dart';

import '../../core/models/map_models.dart';
import '../app/app_controller.dart';
import 'map_canvas.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.controller});

  final AppController controller;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final metadata = controller.selectedMapMetadata;
    final mapData = controller.selectedMapData ?? SweePiMapData.empty;
    final selection = controller.pendingSelection;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: metadata?.mapId,
                  decoration: const InputDecoration(
                    labelText: 'Saved maps',
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
              ),
              const SizedBox(width: 12),
              IconButton.filledTonal(
                tooltip: 'Refresh maps',
                onPressed: controller.isBusy ? null : controller.refreshMaps,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Card(
              clipBehavior: Clip.antiAlias,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: MapCanvas(
                  mapData: mapData,
                  selection: selection,
                  robotPose: controller.robotStatus.pose,
                  onSelectionChanged: controller.setPendingSelection,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              FilledButton.icon(
                onPressed:
                    selection == null || metadata == null || controller.isBusy
                    ? null
                    : () => _addSection(context, mapData, selection),
                icon: const Icon(Icons.add),
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
                icon: const Icon(Icons.clear),
                label: const Text('Clear Selection'),
              ),
            ],
          ),
          const SizedBox(height: 12),
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
    final nameController = TextEditingController();
    try {
      final sectionName = await showDialog<String>(
        context: context,
        builder: (dialogContext) {
          return AlertDialog(
            title: const Text('Name section'),
            content: TextField(
              controller: nameController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Section name',
                border: OutlineInputBorder(),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () {
                  Navigator.of(dialogContext).pop(nameController.text);
                },
                child: const Text('Add'),
              ),
            ],
          );
        },
      );

      if (!mounted || sectionName == null) {
        return;
      }
      await widget.controller.addSectionFromPolygon(
        sectionName,
        selection.toWorldPolygon(mapData),
      );
    } finally {
      nameController.dispose();
    }
  }
}

class _MetadataAndSections extends StatelessWidget {
  const _MetadataAndSections({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final metadata = controller.selectedMapMetadata;
    if (metadata == null) {
      return const Text('No map selected.');
    }

    return SizedBox(
      height: 180,
      child: Card(
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            Text(
              '${metadata.name} (${metadata.mapId})',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Size: ${metadata.width ?? '--'} x ${metadata.height ?? '--'} | '
              'Resolution: ${metadata.resolution}',
            ),
            Text(
              'Updated: ${metadata.updatedAt.isEmpty ? '--' : metadata.updatedAt}',
            ),
            const Divider(),
            if (metadata.sections.isEmpty)
              const Text('No sections saved yet.')
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
                ),
          ],
        ),
      ),
    );
  }
}
