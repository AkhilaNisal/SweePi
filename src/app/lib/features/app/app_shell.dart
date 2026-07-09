import 'package:flutter/material.dart';

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
        return Scaffold(
          appBar: AppBar(
            title: const Text('SweePi'),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Center(
                  child: Text(
                    widget.controller.isConnected
                        ? 'Connected'
                        : 'Disconnected',
                  ),
                ),
              ),
            ],
          ),
          body: screens[_index],
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.monitor_heart_outlined),
                label: 'Status',
              ),
              NavigationDestination(
                icon: Icon(Icons.explore_outlined),
                label: 'Explore',
              ),
              NavigationDestination(
                icon: Icon(Icons.map_outlined),
                label: 'Maps',
              ),
              NavigationDestination(
                icon: Icon(Icons.cleaning_services_outlined),
                label: 'Clean',
              ),
              NavigationDestination(
                icon: Icon(Icons.settings),
                label: 'Settings',
              ),
            ],
            onDestinationSelected: (value) => setState(() => _index = value),
          ),
        );
      },
    );
  }
}
