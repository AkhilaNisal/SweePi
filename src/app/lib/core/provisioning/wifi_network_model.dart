class WifiNetwork {
  const WifiNetwork({required this.ssid, this.rssi, this.security});

  final String ssid;
  final int? rssi;
  final String? security;

  factory WifiNetwork.fromJson(Map<String, dynamic> json) {
    return WifiNetwork(
      ssid: json['ssid'] as String? ?? '',
      rssi: json['rssi'] as int?,
      security: json['security'] as String?,
    );
  }

  Map<String, Object?> toJson() {
    return {'ssid': ssid, 'rssi': rssi, 'security': security};
  }
}
