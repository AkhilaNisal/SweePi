import 'package:flutter/material.dart';

import '../models/map_models.dart';
import '../theme/app_theme.dart';

class AppBackground extends StatelessWidget {
  const AppBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: isDark ? SweePiTheme.darkGradient : SweePiTheme.lightGradient,
      ),
      child: child,
    );
  }
}

class SweePiPanel extends StatelessWidget {
  const SweePiPanel({super.key, required this.child, this.padding});

  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(SweePiRadius.lg),
        border: Border.all(
          color: Theme.of(
            context,
          ).colorScheme.outlineVariant.withValues(alpha: 0.7),
        ),
        boxShadow: SweePiTheme.softShadow(context),
      ),
      child: Padding(
        padding: padding ?? const EdgeInsets.all(SweePiSpacing.lg),
        child: child,
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.icon,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final IconData? icon;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        if (icon != null) ...[
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [colorScheme.primary, colorScheme.secondary],
              ),
              borderRadius: BorderRadius.circular(SweePiRadius.md),
            ),
            child: Icon(icon, color: Colors.white),
          ),
          const SizedBox(width: SweePiSpacing.md),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle!,
                  style: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ],
          ),
        ),
        ?trailing,
      ],
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip({
    super.key,
    required this.label,
    required this.color,
    this.icon,
  });

  final String label;
  final Color color;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: icon == null ? null : Icon(icon, size: 17, color: color),
      label: Text(label),
      labelStyle: TextStyle(color: color, fontWeight: FontWeight.w800),
      backgroundColor: color.withValues(alpha: 0.12),
      side: BorderSide(color: color.withValues(alpha: 0.32)),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SweePiRadius.xl),
      ),
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
    this.subtitle,
    this.child,
  });

  final String title;
  final String value;
  final IconData icon;
  final Color color;
  final String? subtitle;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return SweePiPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(SweePiRadius.md),
                ),
                child: Icon(icon, color: color),
              ),
              const Spacer(),
            ],
          ),
          const SizedBox(height: SweePiSpacing.md),
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: SweePiSpacing.xs),
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: SweePiSpacing.xs),
            Text(
              subtitle!,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (child != null) ...[
            const SizedBox(height: SweePiSpacing.md),
            child!,
          ],
        ],
      ),
    );
  }
}

class RobotBatteryCard extends StatelessWidget {
  const RobotBatteryCard({
    super.key,
    required this.percent,
    required this.charging,
  });

  final int percent;
  final bool charging;

  @override
  Widget build(BuildContext context) {
    final value = (percent.clamp(0, 100)) / 100;
    final color = percent <= 20
        ? SweePiColors.danger
        : percent <= 45
        ? SweePiColors.accent
        : SweePiColors.secondary;
    return MetricCard(
      title: 'Battery',
      value: '$percent%',
      icon: charging ? Icons.battery_charging_full : Icons.battery_5_bar,
      color: color,
      subtitle: charging ? 'Charging now' : 'On battery power',
      child: ClipRRect(
        borderRadius: BorderRadius.circular(SweePiRadius.xl),
        child: LinearProgressIndicator(
          minHeight: 10,
          value: value,
          backgroundColor: color.withValues(alpha: 0.16),
          valueColor: AlwaysStoppedAnimation<Color>(color),
        ),
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
  });

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(SweePiSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: colorScheme.primary),
            const SizedBox(height: SweePiSpacing.md),
            Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: SweePiSpacing.sm),
            Text(
              message,
              style: TextStyle(color: colorScheme.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class ColorfulActionButton extends StatelessWidget {
  const ColorfulActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.color,
    this.tonal = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;
  final bool tonal;

  @override
  Widget build(BuildContext context) {
    final buttonColor = color ?? Theme.of(context).colorScheme.primary;
    final child = FittedBox(
      fit: BoxFit.scaleDown,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [Icon(icon, size: 21), const SizedBox(width: 6), Text(label)],
      ),
    );

    if (tonal) {
      return SizedBox(
        height: 52,
        child: FilledButton.tonal(onPressed: onPressed, child: child),
      );
    }

    return SizedBox(
      height: 52,
      child: FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: buttonColor,
          foregroundColor: Colors.white,
        ),
        child: child,
      ),
    );
  }
}

class ColorfulMapCard extends StatelessWidget {
  const ColorfulMapCard({
    super.key,
    required this.map,
    required this.selected,
    required this.onSelected,
  });

  final SweePiMapMetadata map;
  final bool selected;
  final VoidCallback? onSelected;

  String get formattedResolution {
    final resolution = map.resolution;

    if (resolution == null) {
      return '--';
    }

    return resolution.toStringAsFixed(3);
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final borderColor = selected
        ? colorScheme.primary
        : colorScheme.outlineVariant;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        color: selected
            ? colorScheme.primaryContainer.withValues(alpha: 0.45)
            : colorScheme.surface.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(SweePiRadius.lg),
        border: Border.all(
          color: borderColor,
          width: selected ? 2 : 1,
        ),
        boxShadow: selected ? SweePiTheme.softShadow(context) : null,
      ),
      child: Padding(
        padding: const EdgeInsets.all(SweePiSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: colorScheme.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(SweePiRadius.md),
                  ),
                  child: Icon(
                    Icons.map_rounded,
                    color: colorScheme.primary,
                  ),
                ),
                const SizedBox(width: SweePiSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        map.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .titleSmall
                            ?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        map.mapId,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                if (selected)
                  Icon(
                    Icons.check_circle,
                    color: colorScheme.primary,
                  ),
              ],
            ),
            const SizedBox(height: SweePiSpacing.md),
            Text(
              'Created: ${map.createdAt.isEmpty ? '--' : map.createdAt}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              'Size: ${map.width ?? '--'} × ${map.height ?? '--'}'
                  ' | Resolution: $formattedResolution',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: SweePiSpacing.md),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onSelected,
                icon: Icon(
                  selected ? Icons.visibility : Icons.open_in_new,
                ),
                label: Text(selected ? 'Selected' : 'Open map'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Color statusColorForText(String value, {bool connected = true}) {
  final normalized = value.toLowerCase();
  if (!connected ||
      normalized.contains('offline') ||
      normalized.contains('error') ||
      normalized.contains('fail')) {
    return SweePiColors.danger;
  }
  if (normalized.contains('warn') ||
      normalized.contains('pause') ||
      normalized.contains('unknown')) {
    return SweePiColors.accent;
  }
  if (normalized.contains('idle') ||
      normalized.contains('ready') ||
      normalized.contains('online') ||
      normalized.contains('connected')) {
    return SweePiColors.secondary;
  }
  return SweePiColors.primary;
}
