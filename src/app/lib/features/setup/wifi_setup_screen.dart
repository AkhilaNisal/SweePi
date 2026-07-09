import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/connection/robot_discovered_device.dart';
import '../../core/provisioning/ble_wifi_provisioning_service.dart';
import '../../core/provisioning/provisioning_status_model.dart';
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
  StreamSubscription<ProvisioningStatus>? _statusSubscription;
  WifiNetwork? _selectedNetwork;
  ProvisioningStatus? _lastProvisioningStatus;
  Object? _lastBleError;
  bool _isConnecting = false;
  bool _isPreparingBle = false;
  bool _isLeavingScreen = false;

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
    _statusSubscription = widget.provisioningService.statusStream.listen(
          (status) {
        _lastProvisioningStatus = status;
        _refreshFormState();
      },
      onError: (Object error) {
        _lastBleError = error;
        _refreshFormState();
      },
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _ensureBleReady();
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
    if (!mounted || _isLeavingScreen) {
      return;
    }
    setState(() {
      _selectedNetwork = _networkForSsid(_ssidController.text);
    });
  }

  Future<void> _ensureBleReady() async {
    if (!mounted || _isLeavingScreen || _isPreparingBle) {
      return;
    }

    final alreadyReady =
        widget.provisioningService.isConnected &&
            widget.provisioningService.isProvisioningServiceDiscovered &&
            widget.provisioningService.hasWifiConfigCharacteristic;

    if (alreadyReady) {
      _refreshFormState();
      return;
    }

    setState(() {
      _isPreparingBle = true;
      _lastBleError = null;
    });

    try {
      final robotInfo = await widget.provisioningService.connect(widget.robot);
      await widget.controller.connectionManager.markBleConnected(robotInfo);
    } catch (error) {
      _lastBleError = error;
    } finally {
      if (mounted && !_isLeavingScreen) {
        setState(() {
          _isPreparingBle = false;
          _selectedNetwork = _networkForSsid(_ssidController.text);
        });
      }
    }
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

  WifiConnectBlockReason get _connectBlockReason {
    return wifiConnectBlockReason(
      bleConnected: widget.provisioningService.isConnected,
      provisioningServiceDiscovered:
      widget.provisioningService.isProvisioningServiceDiscovered,
      wifiConfigDiscovered:
      widget.provisioningService.hasWifiConfigCharacteristic,
      ssid: _ssidController.text,
      password: _passwordController.text,
      selectedNetwork: _selectedNetwork,
      isConnecting: _isConnecting,
      isWaitingForProvisioning: _isPreparingBle,
    );
  }

  bool get _canConnectSweePi {
    return _connectBlockReason == WifiConnectBlockReason.none;
  }

  bool _shouldShowBleRecoveryAction(WifiConnectBlockReason reason) {
    return reason == WifiConnectBlockReason.bleNotConnected ||
        reason == WifiConnectBlockReason.provisioningServiceNotFound ||
        reason == WifiConnectBlockReason.wifiConfigCharacteristicNotFound ||
        reason == WifiConnectBlockReason.waitingForProvisioning;
  }

  void _connectSweePi() {
    setState(() => _isConnecting = true);
    _isLeavingScreen = true;
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
  }

  @override
  Widget build(BuildContext context) {
    final selectedNetwork = _selectedNetwork;
    final blockReason = _connectBlockReason;
    final canConnectSweePi = _canConnectSweePi;

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
          if (_isPreparingBle) ...[
            const LinearProgressIndicator(),
            const SizedBox(height: 8),
            Text(
              'Connecting to SweePi Bluetooth setup service...',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
          ],
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
            onPressed: canConnectSweePi ? _connectSweePi : null,
            icon: const Icon(Icons.wifi),
            label: const Text('Connect SweePi'),
          ),
          if (blockReason != WifiConnectBlockReason.none) ...[
            const SizedBox(height: 8),
            Text(
              connectBlockReasonMessage(blockReason),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ],
          if (_shouldShowBleRecoveryAction(blockReason)) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _isPreparingBle ? null : _ensureBleReady,
              icon: _isPreparingBle
                  ? const SizedBox.square(
                dimension: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
                  : const Icon(Icons.bluetooth_connected),
              label: Text(_isPreparingBle ? 'Connecting...' : 'Reconnect to SweePi'),
            ),
          ],
          const SizedBox(height: 12),
          _WifiConnectDebugDetails(
            bleConnected: widget.provisioningService.isConnected,
            provisioningServiceDiscovered:
            widget.provisioningService.isProvisioningServiceDiscovered,
            wifiConfigDiscovered:
            widget.provisioningService.hasWifiConfigCharacteristic,
            selectedNetwork: selectedNetwork,
            ssid: _ssidController.text,
            passwordLength: _passwordController.text.length,
            isConnecting: _isConnecting,
            isPreparingBle: _isPreparingBle,
            blockReason: blockReason,
            lastProvisioningStatus: _lastProvisioningStatus,
            lastBleError: _lastBleError,
          ),
        ],
      ),
    );
  }
}

@visibleForTesting
enum WifiConnectBlockReason {
  none,
  bleNotConnected,
  provisioningServiceNotFound,
  wifiConfigCharacteristicNotFound,
  ssidMissing,
  passwordMissing,
  connecting,
  waitingForProvisioning,
}

@visibleForTesting
WifiConnectBlockReason wifiConnectBlockReason({
  required bool bleConnected,
  required bool provisioningServiceDiscovered,
  required bool wifiConfigDiscovered,
  required String ssid,
  required String password,
  required WifiNetwork? selectedNetwork,
  required bool isConnecting,
  bool isWaitingForProvisioning = false,
}) {
  final hasSsid = ssid.trim().isNotEmpty;
  final normalizedSsid = ssid.trim();
  final isManualNetwork =
      selectedNetwork == null || selectedNetwork.ssid != normalizedSsid;
  final isOpenNetwork = !isManualNetwork && !selectedNetwork.requiresPassword;
  final hasRequiredPassword = isOpenNetwork || password.isNotEmpty;

  if (isConnecting) {
    return WifiConnectBlockReason.connecting;
  }
  if (isWaitingForProvisioning) {
    return WifiConnectBlockReason.waitingForProvisioning;
  }
  if (!bleConnected) {
    return WifiConnectBlockReason.bleNotConnected;
  }
  if (!provisioningServiceDiscovered) {
    return WifiConnectBlockReason.provisioningServiceNotFound;
  }
  if (!wifiConfigDiscovered) {
    return WifiConnectBlockReason.wifiConfigCharacteristicNotFound;
  }
  if (!hasSsid) {
    return WifiConnectBlockReason.ssidMissing;
  }
  if (!hasRequiredPassword) {
    return WifiConnectBlockReason.passwordMissing;
  }
  return WifiConnectBlockReason.none;
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
  bool isWaitingForProvisioning = false,
}) {
  return wifiConnectBlockReason(
    bleConnected: bleConnected,
    provisioningServiceDiscovered: provisioningServiceDiscovered,
    wifiConfigDiscovered: wifiConfigDiscovered,
    ssid: ssid,
    password: password,
    selectedNetwork: selectedNetwork,
    isConnecting: isConnecting,
    isWaitingForProvisioning: isWaitingForProvisioning,
  ) ==
      WifiConnectBlockReason.none;
}

@visibleForTesting
String connectBlockReasonMessage(WifiConnectBlockReason reason) {
  switch (reason) {
    case WifiConnectBlockReason.none:
      return '';
    case WifiConnectBlockReason.bleNotConnected:
      return 'Bluetooth device is not connected.';
    case WifiConnectBlockReason.provisioningServiceNotFound:
      return 'SweePi BLE provisioning service was not discovered.';
    case WifiConnectBlockReason.wifiConfigCharacteristicNotFound:
      return 'Wi-Fi config characteristic was not found.';
    case WifiConnectBlockReason.ssidMissing:
      return 'Enter a Wi-Fi network name.';
    case WifiConnectBlockReason.passwordMissing:
      return 'Enter the Wi-Fi password.';
    case WifiConnectBlockReason.connecting:
      return 'Connecting to Wi-Fi...';
    case WifiConnectBlockReason.waitingForProvisioning:
      return 'Waiting for BLE provisioning status...';
  }
}

class _WifiConnectDebugDetails extends StatelessWidget {
  const _WifiConnectDebugDetails({
    required this.bleConnected,
    required this.provisioningServiceDiscovered,
    required this.wifiConfigDiscovered,
    required this.selectedNetwork,
    required this.ssid,
    required this.passwordLength,
    required this.isConnecting,
    required this.isPreparingBle,
    required this.blockReason,
    required this.lastProvisioningStatus,
    required this.lastBleError,
  });

  final bool bleConnected;
  final bool provisioningServiceDiscovered;
  final bool wifiConfigDiscovered;
  final WifiNetwork? selectedNetwork;
  final String ssid;
  final int passwordLength;
  final bool isConnecting;
  final bool isPreparingBle;
  final WifiConnectBlockReason blockReason;
  final ProvisioningStatus? lastProvisioningStatus;
  final Object? lastBleError;

  @override
  Widget build(BuildContext context) {
    final normalizedSsid = ssid.trim();
    final isManualNetwork =
        selectedNetwork == null || selectedNetwork!.ssid != normalizedSsid;
    final isOpenNetwork =
        !isManualNetwork && selectedNetwork?.requiresPassword == false;
    final textStyle = Theme.of(context).textTheme.bodySmall;

    return ExpansionTile(
      maintainState: true,
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: Text('Debug details', style: textStyle),
      children: [
        _DebugLine(label: 'BLE connected', value: '$bleConnected'),
        _DebugLine(
          label: 'Provisioning service discovered',
          value: '$provisioningServiceDiscovered',
        ),
        _DebugLine(
          label: 'WIFI_CONFIG discovered',
          value: '$wifiConfigDiscovered',
        ),
        _DebugLine(label: 'Selected network', value: selectedNetwork?.ssid),
        _DebugLine(label: 'SSID text', value: ssid),
        _DebugLine(label: 'Password length', value: '$passwordLength'),
        _DebugLine(label: 'Is open network', value: '$isOpenNetwork'),
        _DebugLine(label: 'Is manual network', value: '$isManualNetwork'),
        _DebugLine(label: 'Is connecting', value: '$isConnecting'),
        _DebugLine(label: 'Is preparing BLE', value: '$isPreparingBle'),
        _DebugLine(label: 'Current block reason', value: blockReason.name),
        _DebugLine(
          label: 'Last provisioning status',
          value: lastProvisioningStatus?.state.jsonName,
        ),
        _DebugLine(label: 'Last BLE error', value: lastBleError?.toString()),
      ],
    );
  }
}

class _DebugLine extends StatelessWidget {
  const _DebugLine({required this.label, required this.value});

  final String label;
  final String? value;

  @override
  Widget build(BuildContext context) {
    final textStyle = Theme.of(context).textTheme.bodySmall;
    return Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Text(
          '$label: ${value?.isNotEmpty == true ? value : 'none'}',
          style: textStyle,
        ),
      ),
    );
  }
}