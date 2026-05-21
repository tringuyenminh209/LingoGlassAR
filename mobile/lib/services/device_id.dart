// Stable per-install device UUID. Cached in shared_preferences, generated
// once on first call. Backend POST /v1/sessions accepts this as deviceId
// (Pydantic-validated UUID v4 on the server) and the WS session.start
// event mirrors it.

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class DeviceId {
  DeviceId._();

  static const String _prefsKey = 'lingoglass.device_id';

  /// Returns the cached UUID v4 for this install, generating + persisting
  /// it on first call. Subsequent calls are cheap (single prefs read).
  static Future<String> get() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_prefsKey);
    if (id == null) {
      id = const Uuid().v4();
      await prefs.setString(_prefsKey, id);
    }
    return id;
  }
}
