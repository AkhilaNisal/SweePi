import 'dart:async';
import 'dart:convert';
import 'dart:io';

class RobotApiClient {
  RobotApiClient({
    required this.host,
    required this.apiPort,
    required this.wsPort,
  });

  final String host;
  final int apiPort;
  final int wsPort;

  WebSocket? _webSocket;

  Uri _uri(String path) => Uri.parse('http://$host:$apiPort$path');

  Future<Map<String, dynamic>> getJson(String path) async {
    final request = await HttpClient().getUrl(_uri(path));
    final response = await request.close();
    final body = await response.transform(utf8.decoder).join();
    final data = jsonDecode(body);
    if (data is Map<String, dynamic>) {
      return data;
    }
    throw const FormatException('Expected a JSON object response');
  }

  Future<Map<String, dynamic>> sendJson(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final client = HttpClient();
    final request = switch (method) {
      'POST' => await client.postUrl(_uri(path)),
      'PUT' => await client.putUrl(_uri(path)),
      'DELETE' => await client.deleteUrl(_uri(path)),
      _ => throw ArgumentError('Unsupported method $method'),
    };
    request.headers.contentType = ContentType.json;
    request.write(jsonEncode(body ?? const {}));
    final response = await request.close();
    final payload = await response.transform(utf8.decoder).join();
    final data = jsonDecode(payload);
    if (data is Map<String, dynamic>) {
      return data;
    }
    throw const FormatException('Expected a JSON object response');
  }

  Stream<Map<String, dynamic>> connectWebSocket() async* {
    _webSocket = await WebSocket.connect('ws://$host:$wsPort');
    await for (final message in _webSocket!) {
      if (message is String) {
        final decoded = jsonDecode(message);
        if (decoded is Map<String, dynamic>) {
          yield decoded;
        }
      }
    }
  }

  Future<void> close() async {
    await _webSocket?.close();
    _webSocket = null;
  }
}
