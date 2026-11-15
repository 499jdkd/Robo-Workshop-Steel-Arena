import 'dart:convert';
import 'package:http/http.dart' as http;

/// Optional developer instrumentation. Normal builds have no endpoint.
Future<void> reportProfile(Map<String, Object?> metric) async {
  const endpoint = String.fromEnvironment('RIVE_METRICS_URL');
  if (endpoint.isEmpty) return;
  final uri = Uri.parse(endpoint);
  if (uri.host != '127.0.0.1' && uri.host != 'localhost') return;
  try {
    await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(metric),
        )
        .timeout(const Duration(seconds: 2));
  } catch (_) {
    // A missing local collector must never interfere with the animation.
  }
}
