import 'package:flutter/material.dart';

import 'features/app/app_controller.dart';
import 'features/app/app_shell.dart';

void main() {
  final controller = AppController();
  runApp(SweePiApp(controller: controller));
}

class SweePiApp extends StatelessWidget {
  const SweePiApp({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SweePi',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E6B52),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F7F2),
        useMaterial3: true,
      ),
      home: AppShell(controller: controller),
    );
  }
}
