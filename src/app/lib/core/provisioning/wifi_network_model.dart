class WifiNetwork {
  const WifiNetwork({required this.ssid, this.rssi, this.security});

  final String ssid;
  final int? rssi;
  final String? security;

  bool get requiresPassword => security?.trim().toLowerCase() != 'open';

  factory WifiNetwork.fromJson(Map<String, dynamic> json) {
    return WifiNetwork(
      ssid: json['ssid'] as String? ?? '',
      rssi: _intFromJson(json['rssi'] ?? json['signal']),
      security: json['security'] as String?,
    );
  }

  Map<String, Object?> toJson() {
    return {'ssid': ssid, 'rssi': rssi, 'security': security};
  }

  static int? _intFromJson(Object? value) {
    if (value is int) {
      return value;
    }
    if (value is num) {
      return value.round();
    }
    if (value is String) {
      return int.tryParse(value);
    }
    return null;
  }
}
