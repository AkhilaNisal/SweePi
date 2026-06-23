# sweepi

A new Flutter project.

## API Connection

The default API host and port are configured in:

```text
lib/core/network/robot_api_client.dart
```

For a real Android phone, set `robotIp` to the laptop or robot LAN IP address
that works in the phone browser, for example `192.168.8.101`. Do not use
`localhost`, `127.0.0.1`, or `0.0.0.0` on a real phone because those addresses
refer to the phone itself. The app builds API URLs as:

```text
http://<robotIp>:<robotPort>
```

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
