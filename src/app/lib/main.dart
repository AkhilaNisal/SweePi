import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'features/app/app_controller.dart';
import 'features/app/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController();
  await controller.loadThemeMode();
  runApp(SweePiApp(controller: controller));
}

class SweePiApp extends StatelessWidget {
  const SweePiApp({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return MaterialApp(
          title: 'SweePi',
          debugShowCheckedModeBanner: false,
          theme: SweePiTheme.light,
          darkTheme: SweePiTheme.dark,
          themeMode: controller.themeMode,
          home: AppShell(controller: controller),
        );
      },
    );
  }
}
