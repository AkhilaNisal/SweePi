// ignore_for_file: constant_identifier_names

class SweePiBleUuids {
  const SweePiBleUuids._();

  static const sweepiProvisioningServiceUuid =
      '7a0b0001-4f2a-4f7a-9b7d-9c7b6f000001';
  static const robotInfoCharacteristicUuid =
      '7a0b0002-4f2a-4f7a-9b7d-9c7b6f000001';
  static const wifiScanCharacteristicUuid =
      '7a0b0003-4f2a-4f7a-9b7d-9c7b6f000001';
  static const wifiConfigCharacteristicUuid =
      '7a0b0004-4f2a-4f7a-9b7d-9c7b6f000001';
  static const wifiStatusCharacteristicUuid =
      '7a0b0005-4f2a-4f7a-9b7d-9c7b6f000001';
  static const setupCommandCharacteristicUuid =
      '7a0b0006-4f2a-4f7a-9b7d-9c7b6f000001';

  static const requiredCharacteristicUuids = [
    robotInfoCharacteristicUuid,
    wifiScanCharacteristicUuid,
    wifiConfigCharacteristicUuid,
    wifiStatusCharacteristicUuid,
    setupCommandCharacteristicUuid,
  ];
}

const SWEEPI_PROVISIONING_SERVICE_UUID =
    SweePiBleUuids.sweepiProvisioningServiceUuid;
const ROBOT_INFO_CHARACTERISTIC_UUID =
    SweePiBleUuids.robotInfoCharacteristicUuid;
const WIFI_SCAN_CHARACTERISTIC_UUID = SweePiBleUuids.wifiScanCharacteristicUuid;
const WIFI_CONFIG_CHARACTERISTIC_UUID =
    SweePiBleUuids.wifiConfigCharacteristicUuid;
const WIFI_STATUS_CHARACTERISTIC_UUID =
    SweePiBleUuids.wifiStatusCharacteristicUuid;
const SETUP_COMMAND_CHARACTERISTIC_UUID =
    SweePiBleUuids.setupCommandCharacteristicUuid;

String normalizeUuid(Object? value) {
  return value
      .toString()
      .replaceAll('{', '')
      .replaceAll('}', '')
      .replaceAll(RegExp(r'\s+'), '')
      .toLowerCase();
}

bool uuidEquals(Object? left, Object? right) {
  return normalizeUuid(left) == normalizeUuid(right);
}
