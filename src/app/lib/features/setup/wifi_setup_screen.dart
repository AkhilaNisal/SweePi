import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/connection/robot_discovered_device.dart';
import '../../core/provisioning/ble_wifi_provisioning_service.dart';
import '../../core/provisioning/wifi_network_model.dart';
import '../app/app_controller.dart';
import 'wifi_connecting_screen.dart';

class WifiSetupScreen extends StatefulWidget {
  const WifiSetupScreen({
    super.key,
    required this.controller,
    required this.robot,
    required this.networks,
    required this.provisioningService,
  });

  final AppController controller;
  final RobotDiscoveredDevice robot;
  final List<WifiNetwork> networks;
  final BleWifiProvisioningService provisioningService;

  @override
  State<WifiSetupScreen> createState() => _WifiSetupScreenState();
}

class _WifiSetupScreenState extends State<WifiSetupScreen> {
  late final TextEditingController _ssidController;
  final _passwordController = TextEditingController();
  StreamSubscription? _statusSubscription;
  WifiNetwork? _selectedNetwork;
  bool _isConnecting = false;

  @override
  void initState() {
    super.initState();
    _ssidController = TextEditingController(
      text: widget.networks.isEmpty ? '' : widget.networks.first.ssid,
    );
    _selectedNetwork = _networkForSsid(_ssidController.text);
    _ssidController.addListener(_refreshFormState);
    _passwordController.addListener(_refreshFormState);
    widget.controller.connectionManager.addListener(_refreshFormState);
    _statusSubscription = widget.provisioningService.statusStream.listen((_) {
      _refreshFormState();
    });
  }

  @override
  void dispose() {
    _statusSubscription?.cancel();
    widget.controller.connectionManager.removeListener(_refreshFormState);
    _ssidController.removeListener(_refreshFormState);
    _passwordController.removeListener(_refreshFormState);
    _ssidController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _refreshFormState() {
    if (!mounted) {
      return;
    }
    setState(() {
      _selectedNetwork = _networkForSsid(_ssidController.text);
    });
  }

  WifiNetwork? _networkForSsid(String ssid) {
    final normalizedSsid = ssid.trim();
    for (final network in widget.networks) {
      if (network.ssid == normalizedSsid) {
        return network;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selectedNetwork = _selectedNetwork;
    final canConnect = canConnectToWifi(
      bleConnected: widget.provisioningService.isConnected,
      provisioningServiceDiscovered:
          widget.provisioningService.isProvisioningServiceDiscovered,
      wifiConfigDiscovered:
          widget.provisioningService.hasWifiConfigCharacteristic,
      ssid: _ssidController.text,
      password: _passwordController.text,
      selectedNetwork: selectedNetwork,
      isConnecting: _isConnecting,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Robot Wi-Fi')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Choose a Wi-Fi network',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          if (widget.networks.isNotEmpty)
            for (final network in widget.networks)
              ListTile(
                leading: Icon(
                  selectedNetwork?.ssid == network.ssid
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                ),
                title: Text(network.ssid),
                subtitle: Text(network.security ?? 'Secured network'),
                onTap: () {
                  setState(() {
                    _selectedNetwork = network;
                    _ssidController.text = network.ssid;
                  });
                },
              ),
          TextField(
            controller: _ssidController,
            decoration: const InputDecoration(
              labelText: 'Wi-Fi name',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: !canConnect
                ? null
                : () {
                    setState(() => _isConnecting = true);
                    final password = _passwordController.text;
                    Navigator.of(context).pushReplacement(
                      MaterialPageRoute<void>(
                        builder: (_) => WifiConnectingScreen(
                          controller: widget.controller,
                          robot: widget.robot,
                          ssid: _ssidController.text.trim(),
                          password: password,
                          provisioningService: widget.provisioningService,
                        ),
                      ),
                    );
                    _passwordController.clear();
                  },
            icon: const Icon(Icons.wifi),
            label: const Text('Connect SweePi'),
          ),
        ],
      ),
    );
  }
}

@visibleForTesting
bool canConnectToWifi({
  required bool bleConnected,
  required bool provisioningServiceDiscovered,
  required bool wifiConfigDiscovered,
  required String ssid,
  required String password,
  required WifiNetwork? selectedNetwork,
  required bool isConnecting,
}) {
  if (isConnecting ||
      !bleConnected ||
      !provisioningServiceDiscovered ||
      !wifiConfigDiscovered ||
      ssid.trim().isEmpty) {
    return false;
  }
  final requiresPassword = selectedNetwork?.requiresPassword ?? true;
  return !requiresPassword || password.isNotEmpty;
}
