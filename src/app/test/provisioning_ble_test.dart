import 'package:flutter_test/flutter_test.dart';
import 'package:sweepi/core/provisioning/ble_uuid_constants.dart';
import 'package:sweepi/core/provisioning/ble_wifi_provisioning_service.dart';
import 'package:sweepi/core/provisioning/provisioning_status_model.dart';
import 'package:sweepi/core/provisioning/wifi_network_model.dart';

void main() {
  test('BLE UUID constants match Raspberry Pi provisioning UUIDs', () {
    expect(
      SWEEPI_PROVISIONING_SERVICE_UUID,
      '7a0b0001-4f2a-4f7a-9b7d-9c7b6f000001',
    );
    expect(
      ROBOT_INFO_CHARACTERISTIC_UUID,
      '7a0b0002-4f2a-4f7a-9b7d-9c7b6f000001',
    );
    expect(
      WIFI_SCAN_CHARACTERISTIC_UUID,
      '7a0b0003-4f2a-4f7a-9b7d-9c7b6f000001',
    );
    expect(
      WIFI_CONFIG_CHARACTERISTIC_UUID,
      '7a0b0004-4f2a-4f7a-9b7d-9c7b6f000001',
    );
    expect(
      WIFI_STATUS_CHARACTERISTIC_UUID,
      '7a0b0005-4f2a-4f7a-9b7d-9c7b6f000001',
    );
    expect(
      SETUP_COMMAND_CHARACTERISTIC_UUID,
      '7a0b0006-4f2a-4f7a-9b7d-9c7b6f000001',
    );
  });

  test('UUID comparison is normalized and case-insensitive', () {
    expect(
      uuidEquals(
        ' {7A0B0004-4F2A-4F7A-9B7D-9C7B6F000001} ',
        WIFI_CONFIG_CHARACTERISTIC_UUID,
      ),
      isTrue,
    );
  });

  test('service lookup searches all services and only the SweePi service', () {
    const wrongCharacteristic = _TestCharacteristic(
      id: 'wrong-service',
      uuid: WIFI_CONFIG_CHARACTERISTIC_UUID,
    );
    const targetCharacteristic = _TestCharacteristic(
      id: 'target-service',
      uuid: WIFI_CONFIG_CHARACTERISTIC_UUID,
    );
    final services = [
      const _TestService(
        uuid: '11111111-1111-1111-1111-111111111111',
        characteristics: [wrongCharacteristic],
      ),
      const _TestService(
        uuid: SWEEPI_PROVISIONING_SERVICE_UUID,
        characteristics: [targetCharacteristic],
      ),
    ];

    final found = findSweePiProvisioningCharacteristics(
      services: services,
      requiredCharacteristicUuids: const [WIFI_CONFIG_CHARACTERISTIC_UUID],
      serviceUuidOf: (service) => service.uuid,
      characteristicsOf: (service) => service.characteristics,
      characteristicUuidOf: (characteristic) => characteristic.uuid,
    );

    expect(found[WIFI_CONFIG_CHARACTERISTIC_UUID]?.id, 'target-service');
  });

  test('missing WIFI_CONFIG is absent from discovery results', () {
    final found = findSweePiProvisioningCharacteristics(
      services: const [
        _TestService(
          uuid: SWEEPI_PROVISIONING_SERVICE_UUID,
          characteristics: [
            _TestCharacteristic(
              id: 'status',
              uuid: WIFI_STATUS_CHARACTERISTIC_UUID,
            ),
          ],
        ),
      ],
      requiredCharacteristicUuids: const [WIFI_CONFIG_CHARACTERISTIC_UUID],
      serviceUuidOf: (service) => service.uuid,
      characteristicsOf: (service) => service.characteristics,
      characteristicUuidOf: (characteristic) => characteristic.uuid,
    );

    expect(found, isNot(contains(WIFI_CONFIG_CHARACTERISTIC_UUID)));
  });

  test(
    'Wi-Fi scan response parsing accepts RPi signal and security fields',
    () {
      final network = WifiNetwork.fromJson(const {
        'ssid': 'akhila',
        'signal': 85,
        'security': 'WPA/WPA2',
      });

      expect(network.ssid, 'akhila');
      expect(network.rssi, 85);
      expect(network.security, 'WPA/WPA2');
      expect(network.requiresPassword, isTrue);
      expect(
        WifiNetwork.fromJson(const {
          'ssid': 'guest',
          'security': 'open',
        }).requiresPassword,
        isFalse,
      );
    },
  );

  test('Wi-Fi status response parsing accepts RPi connected payload', () {
    final status = ProvisioningStatus.fromJson(const {
      'state': 'connected',
      'message': 'Connected to Wi-Fi',
      'ssid': 'akhila',
      'ip': '192.168.8.106',
      'hostname': 'sweepi-dev-001.local',
      'robot_id': 'sweepi-dev-001',
    });

    expect(status.state, WifiProvisioningState.connected);
    expect(status.isConnected, isTrue);
    expect(status.ip, '192.168.8.106');
    expect(status.hostname, 'sweepi-dev-001.local');
    expect(status.robotId, 'sweepi-dev-001');
  });

  test('netplan_wifi status is treated as an idle provisioning state', () {
    final status = ProvisioningStatus.fromJson(const {'state': 'netplan_wifi'});

    expect(status.state, WifiProvisioningState.idle);
  });
}

class _TestService {
  const _TestService({required this.uuid, required this.characteristics});

  final String uuid;
  final List<_TestCharacteristic> characteristics;
}

class _TestCharacteristic {
  const _TestCharacteristic({required this.id, required this.uuid});

  final String id;
  final String uuid;
}
