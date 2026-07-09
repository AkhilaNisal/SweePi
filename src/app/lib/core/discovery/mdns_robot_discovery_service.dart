import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:multicast_dns/multicast_dns.dart';

import '../connection/robot_channel.dart';
import '../connection/robot_discovered_device.dart';

abstract class RobotMdnsDiscoveryService {
  Future<List<RobotDiscoveredDevice>> discover({
    Duration timeout = const Duration(seconds: 4),
  });
}

class MulticastMdnsRobotDiscoveryService implements RobotMdnsDiscoveryService {
  static const serviceType = '_sweepi._tcp.local';

  const MulticastMdnsRobotDiscoveryService();

  @override
  Future<List<RobotDiscoveredDevice>> discover({
    Duration timeout = const Duration(seconds: 4),
  }) async {
    final client = MDnsClient();
    try {
      await client.start();
      final ptrRecords = await client
          .lookup<PtrResourceRecord>(
            ResourceRecordQuery.serverPointer(serviceType),
            timeout: timeout,
          )
          .toList();

      final robots = <RobotDiscoveredDevice>[];
      for (final ptr in ptrRecords) {
        final serviceName = ptr.domainName;
        final srv = await _firstOrNull(
          client.lookup<SrvResourceRecord>(
            ResourceRecordQuery.service(serviceName),
            timeout: timeout,
          ),
        );
        if (srv == null) {
          continue;
        }

        final txtRecords = await client
            .lookup<TxtResourceRecord>(
              ResourceRecordQuery.text(serviceName),
              timeout: timeout,
            )
            .toList();
        final txt = _parseTxtRecords(txtRecords);
        final ipAddress = await _resolveIpAddress(client, srv.target, timeout);
        final robotId = txt['robot_id'] ?? _robotIdFromServiceName(serviceName);
        final name = txt['name'] ?? _friendlyNameFromRobotId(robotId);
        final apiPort = _parsePort(txt['api']) ?? srv.port;
        final websocketPort = _parsePort(txt['ws']) ?? 8765;

        robots.add(
          RobotDiscoveredDevice(
            robotId: robotId,
            name: name,
            channel: RobotChannel.wifi,
            hostName: srv.target,
            ipAddress: ipAddress,
            apiPort: apiPort,
            websocketPort: websocketPort,
            serviceName: serviceName,
            model: txt['model'],
            txtRecords: txt,
            status: txt['status'],
          ),
        );
      }
      return robots;
    } catch (error) {
      debugPrint('[mDNS] SweePi discovery failed: $error');
      return const [];
    } finally {
      client.stop();
    }
  }

  Future<T?> _firstOrNull<T>(Stream<T> stream) async {
    try {
      return await stream.first;
    } on StateError {
      return null;
    }
  }

  Future<String?> _resolveIpAddress(
    MDnsClient client,
    String host,
    Duration timeout,
  ) async {
    final ipv4 = await _firstOrNull(
      client.lookup<IPAddressResourceRecord>(
        ResourceRecordQuery.addressIPv4(host),
        timeout: timeout,
      ),
    );
    if (ipv4 != null) {
      return ipv4.address.address;
    }

    final ipv6 = await _firstOrNull(
      client.lookup<IPAddressResourceRecord>(
        ResourceRecordQuery.addressIPv6(host),
        timeout: timeout,
      ),
    );
    return ipv6?.address.address;
  }

  Map<String, String> _parseTxtRecords(List<TxtResourceRecord> records) {
    final txt = <String, String>{};
    for (final record in records) {
      final parts = record.text
          .split(RegExp(r'[\x00\r\n]+'))
          .where((part) => part.trim().isNotEmpty);
      for (final part in parts) {
        final index = part.indexOf('=');
        if (index <= 0) {
          txt[part.trim()] = 'true';
          continue;
        }
        txt[part.substring(0, index).trim()] = part.substring(index + 1).trim();
      }
    }
    return txt;
  }

  int? _parsePort(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    return int.tryParse(value);
  }

  String _robotIdFromServiceName(String serviceName) {
    final raw = serviceName.split('.').first.trim();
    return raw.isEmpty ? 'sweepi-unknown' : raw.toLowerCase();
  }

  String _friendlyNameFromRobotId(String robotId) {
    if (robotId.toLowerCase().startsWith('sweepi-')) {
      final suffix = robotId.substring('sweepi-'.length).toUpperCase();
      return 'SweePi-$suffix';
    }
    return robotId;
  }
}

class MockMdnsRobotDiscoveryService implements RobotMdnsDiscoveryService {
  const MockMdnsRobotDiscoveryService({this.shouldFindRobot = true});

  final bool shouldFindRobot;

  @override
  Future<List<RobotDiscoveredDevice>> discover({
    Duration timeout = const Duration(seconds: 4),
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!shouldFindRobot) {
      return const [];
    }
    return [
      RobotDiscoveredDevice(
        robotId: 'sweepi-8f23',
        name: 'SweePi-8F23',
        channel: RobotChannel.wifi,
        hostName: 'sweepi-8f23.local',
        ipAddress: '192.168.1.45',
        apiPort: 8080,
        websocketPort: 8765,
        serviceName: 'SweePi-8F23._sweepi._tcp.local',
        model: 'sweepi',
        txtRecords: const {
          'robot_id': 'sweepi-8f23',
          'model': 'sweepi',
          'api': '8080',
          'ws': '8765',
        },
        status: 'ready',
      ),
    ];
  }
}
