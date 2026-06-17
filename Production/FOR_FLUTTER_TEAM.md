# API Documentation for Flutter Team

# Bump Detection API - Simple Integration Guide

## Quick Start

### 1. Start the API Server

```bash
cd Production
python api_server.py
```

Server will run on: `http://0.0.0.0:8000`

### 2. Test from your computer

```bash
curl http://localhost:8000/
```

### 3. From Flutter app (same WiFi)

```dart
const String apiUrl = "http://192.168.1.50:8000";  // Replace with server IP
```

---

## API Endpoints

### 1. GET / (Server Info)

**URL:** `http://SERVER_IP:8000/`

**Response:**

```json
{
  "service": "Bump Detection API",
  "version": "3.0",
  "total_bumps": 42,
  "dedup_radius_m": 8,
  "status": "running"
}
```

---

### 2. GET /get_bumps (Get All Bumps)

**URL:** `http://SERVER_IP:8000/get_bumps`

**Query Parameters:**

- `limit` (optional): Number of bumps to return (default: 100)
- `min_confirmations` (optional): only return bumps confirmed by at least this many
  unique devices, i.e. `len(reported_by) >= min_confirmations` (default: 1 = all).
  Use `min_confirmations=2` to show only bumps that more than one device has seen.

**Example:**

```
GET http://192.168.1.50:8000/get_bumps?limit=10&min_confirmations=1
```

**Response:**

```json
{
  "total": 2,
  "min_confirmations": 1,
  "bumps": [
    {
      "id": "bump_0000",
      "latitude": 30.04445,
      "longitude": 31.235689,
      "confidence": 0.87,
      "timestamp": "2024-12-19T23:00:00Z",
      "last_seen": "2024-12-19T23:10:00Z",
      "reports_count": 3,
      "reported_by": ["pi_dca632abc123"],
      "altitude": 45.6
    },
    {
      "id": "bump_0001",
      "latitude": 30.044512,
      "longitude": 31.235702,
      "confidence": 0.92,
      "timestamp": "2024-12-19T23:05:00Z",
      "last_seen": "2024-12-19T23:05:00Z",
      "reports_count": 1,
      "reported_by": ["pi_dca632abc123"],
      "altitude": 46.2
    }
  ]
}
```

> Note: `id` is now zero-padded (`bump_0000`). `altitude` is only present if the
> device sent it. Extra fields (`last_seen`, `reports_count`, `reported_by`) are
> safe to ignore in the app if you don't need them.

---

### 3. POST /report_bump (Report New Bump)

**URL:** `http://SERVER_IP:8000/report_bump`

**Request Body:**

```json
{
  "latitude": 30.0444,
  "longitude": 31.2357,
  "confidence": 0.87,
  "timestamp": "2024-12-19T23:00:00Z",
  "altitude": 45.6,
  "device_id": "phone_user123"
}
```

> Only `latitude`, `longitude`, and `confidence` are required. `timestamp`,
> `altitude`, and `device_id` are optional. Sending a `device_id` lets the server
> count how many distinct devices confirmed a bump (powers `min_confirmations`).

**Response (new bump):**

```json
{
  "status": "success",
  "bump_id": "bump_0002",
  "reports_count": 1
}
```

**Response (bump already existed within 8 m — merged, not duplicated):**

```json
{
  "status": "merged",
  "bump_id": "bump_0002",
  "reports_count": 4,
  "message": "Bump already known — updated (now 4 reports)"
}
```

> The server automatically de-duplicates: a report within **8 m** of an existing
> bump updates that bump instead of creating a new one. Check `status` to tell a
> brand-new bump (`success`) from a known one (`merged`).

---

### 4. DELETE /clear_bumps (Clear All - Testing Only)

**URL:** `http://SERVER_IP:8000/clear_bumps`

**Response:**

```json
{
  "status": "success",
  "message": "All bumps cleared"
}
```

---

## Flutter Integration

### Install Dependencies

```yaml
# pubspec.yaml
dependencies:
  http: ^1.1.0
  google_maps_flutter: ^2.5.0
  sqflite: ^2.3.0
```

### API Service Class

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class BumpApiService {
  static const String baseUrl = 'http://192.168.1.50:8000';  // Update this!

  // Get all bumps
  Future<List<Bump>> getBumps({int limit = 100}) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/get_bumps?limit=$limit'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final bumps = (data['bumps'] as List)
            .map((json) => Bump.fromJson(json))
            .toList();
        return bumps;
      } else {
        throw Exception('Failed to load bumps');
      }
    } catch (e) {
      throw Exception('Connection error: $e');
    }
  }

  // Report a bump (if user manually marks one)
  Future<bool> reportBump(double lat, double lng) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/report_bump'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'latitude': lat,
          'longitude': lng,
          'confidence': 1.0,
          'timestamp': DateTime.now().toUtc().toIso8601String(),
        }),
      );

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // Check connection
  Future<bool> checkConnection() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/'),
      ).timeout(const Duration(seconds: 3));

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}
```

### Bump Model Class

```dart
class Bump {
  final String id;
  final double latitude;
  final double longitude;
  final double confidence;
  final String timestamp;
  final double? altitude;

  Bump({
    required this.id,
    required this.latitude,
    required this.longitude,
    required this.confidence,
    required this.timestamp,
    this.altitude,
  });

  factory Bump.fromJson(Map<String, dynamic> json) {
    return Bump(
      id: json['id'],
      latitude: json['latitude'],
      longitude: json['longitude'],
      confidence: json['confidence'],
      timestamp: json['timestamp'],
      altitude: json['altitude'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'latitude': latitude,
      'longitude': longitude,
      'confidence': confidence,
      'timestamp': timestamp,
      'altitude': altitude,
    };
  }
}
```

### Usage Example

```dart
// In your Flutter app
final apiService = BumpApiService();

// Check connection
bool connected = await apiService.checkConnection();
if (connected) {
  print('✓ Connected to API');

  // Get bumps
  List<Bump> bumps = await apiService.getBumps(limit: 50);
  print('Found ${bumps.length} bumps');

  // Display on map (you implement this part)
  for (var bump in bumps) {
    // Add marker to Google Map
    // addMarker(LatLng(bump.latitude, bump.longitude));
  }
} else {
  print('✗ Cannot connect to API');
}
```

---

## Google Maps Display

```dart
import 'package:google_maps_flutter/google_maps_flutter.dart';

GoogleMap(
  initialCameraPosition: CameraPosition(
    target: LatLng(30.0444, 31.2357),  // Cairo
    zoom: 14,
  ),
  markers: bumps.map((bump) {
    return Marker(
      markerId: MarkerId(bump.id),
      position: LatLng(bump.latitude, bump.longitude),
      infoWindow: InfoWindow(
        title: 'Speed Bump',
        snippet: 'Detected: ${bump.timestamp}',
      ),
      icon: BitmapDescriptor.defaultMarkerWithHue(
        BitmapDescriptor.hueRed,
      ),
    );
  }).toSet(),
)
```

---

## JSON Data Format

### Single Bump Object

```json
{
  "id": "bump_0000",
  "latitude": 30.04445,
  "longitude": 31.235689,
  "confidence": 0.87,
  "timestamp": "2024-12-19T23:00:00Z",
  "last_seen": "2024-12-19T23:10:00Z",
  "reports_count": 3,
  "reported_by": ["pi_dca632abc123"],
  "altitude": 45.6
}
```

### Field Descriptions

| Field         | Type     | Description                                            |
| ------------- | -------- | ------------------------------------------------------ |
| id            | string   | Unique bump identifier (zero-padded, e.g. `bump_0000`) |
| latitude      | number   | GPS latitude (-90 to 90)                               |
| longitude     | number   | GPS longitude (-180 to 180)                            |
| confidence    | number   | Highest detection confidence seen (0.0 to 1.0)         |
| timestamp     | string   | ISO 8601 UTC — when the bump was first recorded        |
| last_seen     | string   | ISO 8601 UTC — most recent time it was reported        |
| reports_count | number   | How many times this bump has been reported total       |
| reported_by   | string[] | Unique device IDs that confirmed this bump             |
| altitude      | number   | Altitude in meters (optional — may be absent)          |

---

## Testing Steps

### 1. Test API locally

```bash
# Terminal 1: Start server
python Production/api_server.py

# Terminal 2: Test
curl http://localhost:8000/get_bumps
```

### 2. Get some test data

```bash
# Add a test bump
curl -X POST http://localhost:8000/report_bump \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 30.0444,
    "longitude": 31.2357,
    "confidence": 0.9
  }'

# Get it back
curl http://localhost:8000/get_bumps
```

### 3. Test from Flutter

```dart
void testApi() async {
  final service = BumpApiService();

  // Test connection
  bool connected = await service.checkConnection();
  print('Connected: $connected');

  // Get bumps
  if (connected) {
    List<Bump> bumps = await service.getBumps();
    print('Total bumps: ${bumps.length}');

    for (var bump in bumps) {
      print('Bump at: ${bump.latitude}, ${bump.longitude}');
    }
  }
}
```

---

## Important Notes

### Server IP

- **On Laptop:** Use `localhost` or `127.0.0.1`
- **On Raspberry Pi:** Use Pi's actual IP (get with `hostname -I`)
- **From Mobile:** Use server's network IP (e.g., `192.168.1.50`)

### CORS

API has CORS enabled - you can connect from any origin.

### Data Persistence

Data is saved in `bumps_data.json` file on the server.

### Offline Mode

Flutter app should:

1. Try to connect to API
2. If fails, use cached data from SQLite
3. Retry connection periodically

---

## What You DON'T Need

❌ YOLO model
❌ Camera access
❌ GPS hardware
❌ Python environment
❌ AI/ML knowledge

## What You DO Need

✅ HTTP client (package: `http`)
✅ JSON parsing
✅ Google Maps (package: `google_maps_flutter`)
✅ Local storage (package: `sqflite`)
✅ Network connectivity check

---

## Questions?

If you need:

- Different API endpoints
- Different JSON format
- Additional fields
- WebSockets for real-time updates

Just ask!

---

**Server Location:**

```
Production/api_server.py
```

**Run with:**

```bash
python Production/api_server.py
```

**That's it! Simple. 🎯**
