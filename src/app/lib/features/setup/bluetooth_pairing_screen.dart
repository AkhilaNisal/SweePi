import 'package:flutter/material.dart';

import '../../core/connection/robot_discovered_device.dart';
import '../../core/provisioning/ble_wifi_provisioning_service.dart';
import '../../core/provisioning/wifi_network_model.dart';
import '../app/app_controller.dart';
import 'wifi_setup_screen.dart';

class BluetoothPairingScreen extends StatefulWidget {
  BluetoothPairingScreen({
    super.key,
    required this.controller,
    required this.robot,
    BleWifiProvisioningService? provisioningService,
  }) : provisioningService =
           provisioningService ?? FlutterBlueBleWifiProvisioningService();

  final AppController controller;
  final RobotDiscoveredDevice robot;
  final BleWifiProvisioningService provisioningService;

  @override
  State<BluetoothPairingScreen> createState() => _BluetoothPairingScreenState();
}

class _BluetoothPairingScreenState extends State<BluetoothPairingScreen> {
  bool _loading = true;
  String? _error;
  RobotDiscoveredDevice? _robotInfo;
  List<WifiNetwork> _networks = const [];

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final robotInfo = await widget.provisioningService.connect(widget.robot);
      await widget.controller.connectionManager.markBleConnected(robotInfo);
      final networks = await widget.provisioningService.scanWifiNetworks();
      if (!mounted) {
        return;
      }
      setState(() {
        _robotInfo = robotInfo;
        _networks = networks;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = '$error';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bluetooth setup')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _loading
            ? const _ProgressMessage(message: 'SweePi found nearby')
            : _error != null
            ? _ErrorMessage(message: _error!, onRetry: _connect)
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _robotInfo?.name ?? widget.robot.name,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  const Text('Bluetooth is connected for setup and recovery.'),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: () {
                      Navigator.of(context).pushReplacement(
                        MaterialPageRoute<void>(
                          builder: (_) => WifiSetupScreen(
                            controller: widget.controller,
                            robot: _robotInfo ?? widget.robot,
                            networks: _networks,
                            provisioningService: widget.provisioningService,
                          ),
                        ),
                      );
                    },
                    icon: const Icon(Icons.wifi),
                    label: const Text('Choose Wi-Fi'),
                  ),
                ],
              ),
      ),
    );
  }
}

class _ProgressMessage extends StatelessWidget {
  const _ProgressMessage({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(message),
        ],
      ),
    );
  }
}

class _ErrorMessage extends StatelessWidget {
  const _ErrorMessage({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          message,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Try again'),
        ),
      ],
    );
  }
}
