enum RobotChannel { none, wifi, bluetooth, both }

extension RobotChannelLabel on RobotChannel {
  String get label {
    switch (this) {
      case RobotChannel.none:
        return 'None';
      case RobotChannel.wifi:
        return 'Wi-Fi';
      case RobotChannel.bluetooth:
        return 'Bluetooth';
      case RobotChannel.both:
        return 'Wi-Fi + Bluetooth';
    }
  }
}
