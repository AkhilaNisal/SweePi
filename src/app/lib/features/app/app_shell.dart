import 'package:flutter/material.dart';

import '../../core/widgets/sweepi_widgets.dart';
import '../cleaning/cleaning_screen.dart';
import '../exploration/exploration_screen.dart';
import '../map/map_screen.dart';
import '../setup/robot_discovery_screen.dart';
import '../settings/settings_screen.dart';
import '../status/status_screen.dart';
import 'app_controller.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.controller});

  final AppController controller;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final screens = [
          widget.controller.isConnected
              ? StatusScreen(controller: widget.controller)
              : RobotDiscoveryScreen(controller: widget.controller),
          ExplorationScreen(controller: widget.controller),
          MapScreen(controller: widget.controller),
          CleaningScreen(controller: widget.controller),
          SettingsScreen(controller: widget.controller),
        ];
        final connectionColor = widget.controller.isConnected
            ? statusColorForText('connected')
            : statusColorForText('offline', connected: false);
        return Scaffold(
          extendBody: true,
          appBar: AppBar(
            title: const Text('SweePi'),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: Center(
                  child: StatusChip(
                    label: widget.controller.isConnected
                        ? 'Connected'
                        : 'Offline',
                    icon: widget.controller.isConnected
                        ? Icons.wifi_rounded
                        : Icons.wifi_off_rounded,
                    color: connectionColor,
                  ),
                ),
              ),
            ],
          ),
          body: screens[_index],
          bottomNavigationBar: Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(28),
              child: NavigationBar(
                selectedIndex: _index,
                height: 72,
                destinations: const [
                  NavigationDestination(
                    selectedIcon: Icon(Icons.monitor_heart_rounded),
                    icon: Icon(Icons.monitor_heart_outlined),
                    label: 'Status',
                  ),
                  NavigationDestination(
                    selectedIcon: Icon(Icons.explore_rounded),
                    icon: Icon(Icons.explore_outlined),
                    label: 'Explore',
                  ),
                  NavigationDestination(
                    selectedIcon: Icon(Icons.map_rounded),
                    icon: Icon(Icons.map_outlined),
                    label: 'Maps',
                  ),
                  NavigationDestination(
                    selectedIcon: Icon(Icons.cleaning_services_rounded),
                    icon: Icon(Icons.cleaning_services_outlined),
                    label: 'Clean',
                  ),
                  NavigationDestination(
                    selectedIcon: Icon(Icons.settings_rounded),
                    icon: Icon(Icons.settings_outlined),
                    label: 'Settings',
                  ),
                ],
                onDestinationSelected: (value) =>
                    setState(() => _index = value),
              ),
            ),
          ),
        );
      },
    );
  }
}
