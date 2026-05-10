import 'package:flutter/material.dart';

import '../control/control_screen.dart';
import '../map/map_screen.dart';
import '../schedules/schedules_screen.dart';
import '../settings/settings_screen.dart';
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
          ControlScreen(controller: widget.controller),
          MapScreen(controller: widget.controller),
          SchedulesScreen(controller: widget.controller),
          SettingsScreen(controller: widget.controller),
        ];
        return Scaffold(
          appBar: AppBar(
            title: const Text('SweePi Control'),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Center(
                  child: Text(
                    widget.controller.isConnected ? 'Connected' : 'Disconnected',
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
                icon: Icon(Icons.tune),
                label: 'Control',
              ),
              NavigationDestination(
                icon: Icon(Icons.map_outlined),
                label: 'Map',
              ),
              NavigationDestination(
                icon: Icon(Icons.schedule),
                label: 'Schedules',
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
