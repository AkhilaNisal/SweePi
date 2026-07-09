enum WifiProvisioningState {
  idle,
  scanning,
  connecting,
  connected,
  failedAuth,
  failedNotFound,
  failedTimeout,
  failedUnknown,
}

extension WifiProvisioningStateJson on WifiProvisioningState {
  String get jsonName {
    switch (this) {
      case WifiProvisioningState.idle:
        return 'idle';
      case WifiProvisioningState.scanning:
        return 'scanning';
      case WifiProvisioningState.connecting:
        return 'connecting';
      case WifiProvisioningState.connected:
        return 'connected';
      case WifiProvisioningState.failedAuth:
        return 'failed_auth';
      case WifiProvisioningState.failedNotFound:
        return 'failed_not_found';
      case WifiProvisioningState.failedTimeout:
        return 'failed_timeout';
      case WifiProvisioningState.failedUnknown:
        return 'failed_unknown';
    }
  }

  static WifiProvisioningState fromJsonName(String? value) {
    switch (value) {
      case 'idle':
      case 'netplan_wifi':
        return WifiProvisioningState.idle;
      case 'scanning':
        return WifiProvisioningState.scanning;
      case 'connecting':
        return WifiProvisioningState.connecting;
      case 'connected':
        return WifiProvisioningState.connected;
      case 'failed_auth':
        return WifiProvisioningState.failedAuth;
      case 'failed_not_found':
        return WifiProvisioningState.failedNotFound;
      case 'failed_timeout':
        return WifiProvisioningState.failedTimeout;
      default:
        return WifiProvisioningState.failedUnknown;
    }
  }
}

class ProvisioningStatus {
  const ProvisioningStatus({
    required this.state,
    this.ssid,
    this.ip,
    this.hostname,
    this.robotId,
    this.message,
  });

  final WifiProvisioningState state;
  final String? ssid;
  final String? ip;
  final String? hostname;
  final String? robotId;
  final String? message;

  bool get isConnected => state == WifiProvisioningState.connected;
  bool get isFailure =>
      state == WifiProvisioningState.failedAuth ||
      state == WifiProvisioningState.failedNotFound ||
      state == WifiProvisioningState.failedTimeout ||
      state == WifiProvisioningState.failedUnknown;

  factory ProvisioningStatus.fromJson(Map<String, dynamic> json) {
    return ProvisioningStatus(
      state: WifiProvisioningStateJson.fromJsonName(json['state'] as String?),
      ssid: json['ssid'] as String?,
      ip: json['ip'] as String?,
      hostname: json['hostname'] as String?,
      robotId: json['robot_id'] as String?,
      message: json['message'] as String?,
    );
  }

  Map<String, Object?> toJson() {
    return {
      'state': state.jsonName,
      'ssid': ssid,
      'ip': ip,
      'hostname': hostname,
      'robot_id': robotId,
      'message': message,
    };
  }
}
