import 'package:flutter/material.dart';

import '../app/app_controller.dart';

class SchedulesScreen extends StatelessWidget {
  const SchedulesScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text('Schedules are not part of the current mock API integration.'),
      ),
    );
  }
}
