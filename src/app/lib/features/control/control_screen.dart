import 'package:flutter/material.dart';

import '../app/app_controller.dart';
import '../status/status_screen.dart';

class ControlScreen extends StatelessWidget {
  const ControlScreen({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return StatusScreen(controller: controller);
  }
}
