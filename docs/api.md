# SweePi API Guide

The current mobile app talks to the SweePi API over plain HTTP JSON. This
document lists only the endpoints currently used by the Flutter app and
implemented by the mock API server in `development/mock_api_server`.

Primary implementation references:

```text
src/app/lib/core/network/robot_api_client.dart
development/mock_api_server/app/routers
development/mock_api_server/app/models
development/mock_api_server/app/core/state.py
```

## Base URL And Authentication

```text
HTTP base URL: http://<robot-ip>:8080
API prefix:    /api
```

Local mock server example:

```text
http://localhost:8080/api/robot/status
```

The current API has no authentication requirement. The mock server enables CORS
for local development and accepts requests from the Flutter app, browser, curl,
and Postman.

For a real Android phone, configure the mobile app with the laptop or robot LAN
IP address. Do not use `localhost`, `127.0.0.1`, or `0.0.0.0` on the phone,
because those addresses refer to the phone itself.

The app defaults are in:

```text
src/app/lib/core/network/robot_api_client.dart
```

## Setup Commands

Install mock API server dependencies:

```bash
cd development/mock_api_server
python -m pip install -r requirements.txt
```

Install Flutter app dependencies:

```bash
cd src/app
flutter pub get
```

## Start Commands

Start the mock API server:

```bash
cd development/mock_api_server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

On Windows, the helper script also checks for `fastapi` and `uvicorn` before
starting the server:

```bat
development\mock_api_server\run_mock_server.bat
```

## Run Commands

Run the Flutter app from the app project:

```bash
cd src/app
flutter run
```

Check the mock API from a terminal:

```bash
curl http://localhost:8080/api/robot/status
```

Open the mock server's generated OpenAPI docs while it is running:

```text
http://localhost:8080/docs
```

## Current Mobile App Flow

1. Connect and load status with `GET /api/robot/status`.
2. Load exploration status with `GET /api/exploration/status`.
3. Load saved map metadata with `GET /api/maps`.
4. Select a map with `GET /api/maps/{map_id}` and
   `GET /api/maps/{map_id}/metadata`.
5. Start exploration with `POST /api/exploration/start`.
6. In manual exploration, repeatedly call `POST /api/exploration/manual-drive`
   while a drive button is held.
7. Stop exploration with `POST /api/exploration/stop`; the response returns
   the saved `map_id`.
8. Add sections locally in the app and save them with
   `PUT /api/maps/{map_id}/metadata`.
9. Start cleaning with `POST /api/cleaning/start`.
10. Pause, resume, or stop cleaning with the cleaning command endpoints.

## Response And Error Rules

All documented endpoints return JSON.

The mock server uses FastAPI/Pydantic, so malformed JSON or schema validation
errors return HTTP `422`. Unknown routes return HTTP `404`.

Some valid commands that cannot be performed in the current robot state return
HTTP `200` with `"accepted": false`. Examples include manual drive commands
outside manual exploration and cleaning a missing map.

This guide intentionally omits prototype and historical API surfaces that are
not implemented by the current mobile/mock flow.

## Endpoints

### GET /api/robot/status

Returns the current robot state.

Request body: none.

Curl:

```bash
curl http://localhost:8080/api/robot/status
```

Current mock response shape:

```json
{
  "robot_id": "sweepi-mock-001",
  "state": "idle",
  "mode": "automatic",
  "battery": {
    "percent": 87,
    "charging": false
  },
  "pose": {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "frame": "map"
  },
  "map": {
    "map_id": "my_room_map"
  },
  "cleaning": {
    "task_id": null,
    "map_id": null,
    "sections": [],
    "progress_percent": 0.0
  },
  "nav": {
    "execution_status": "IDLE"
  },
  "errors": [],
  "warnings": []
}
```

The mobile app reads `robot_id`, `state`, `mode`, `battery`, `pose`, `map`,
`cleaning`, `nav`, `errors`, and `warnings`.

### POST /api/exploration/start

Starts an exploration session.

Request body:

```json
{
  "map_name": "bedroom",
  "mode": "automatic"
}
```

Fields:

| Field | Required | Values | Notes |
|---|---:|---|---|
| `map_name` | yes | string | User-facing name for the map to save later. |
| `mode` | yes | `automatic`, `manual` | The app sends one of these two modes. |

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"map_name":"bedroom","mode":"automatic"}'
```

Response:

```json
{
  "accepted": true,
  "state": "exploring",
  "mode": "automatic",
  "map_name": "bedroom",
  "message": "Exploration started"
}
```

### GET /api/exploration/status

Returns the latest exploration state.

Request body: none.

Curl:

```bash
curl http://localhost:8080/api/exploration/status
```

Response while exploration is active:

```json
{
  "state": "exploring",
  "mode": "manual",
  "map_name": "bedroom",
  "map_available": false,
  "message": "Mock exploration running"
}
```

Response while exploration is inactive:

```json
{
  "state": "idle",
  "mode": "automatic",
  "map_name": null,
  "map_available": true,
  "message": "Exploration is not running"
}
```

### POST /api/exploration/manual-drive

Sends a button-style drive command during manual exploration.

Request body:

```json
{
  "command": "forward",
  "speed": 0.2
}
```

Fields:

| Field | Required | Values | Notes |
|---|---:|---|---|
| `command` | yes | `forward`, `backward`, `rotate_left`, `rotate_right`, `stop` | The mobile app sends repeated movement commands while a button is held. |
| `speed` | no | `0.0` to `1.0` | Defaults to `0.2` in the mock model. |

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/manual-drive \
  -H "Content-Type: application/json" \
  -d '{"command":"forward","speed":0.2}'
```

Accepted response:

```json
{
  "accepted": true,
  "command": "forward",
  "speed": 0.2,
  "message": "Mock robot command: forward"
}
```

Rejected response when the robot is not in manual exploration:

```json
{
  "accepted": false,
  "message": "Manual drive is allowed only during manual exploration"
}
```

### POST /api/exploration/stop

Stops exploration and saves a mock map.

Request body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/stop
```

Response:

```json
{
  "accepted": true,
  "state": "idle",
  "map_saved": true,
  "map_id": "map_abc123",
  "message": "Exploration stopped and mock map saved"
}
```

The mobile app stores `map_id`, refreshes saved maps, and selects the saved map.

### GET /api/maps

Returns metadata for all saved maps.

Request body: none.

Curl:

```bash
curl http://localhost:8080/api/maps
```

Response:

```json
{
  "items": [
    {
      "map_id": "my_room_map",
      "name": "My Room",
      "created_at": "2026-06-23T00:00:00+05:30",
      "updated_at": "2026-06-23T16:36:13.499284",
      "width": 99,
      "height": 99,
      "resolution": 0.05,
      "sections": []
    }
  ]
}
```

The list endpoint returns metadata only. Fetch occupancy data with
`GET /api/maps/{map_id}`.

### GET /api/maps/{map_id}

Returns occupancy data for a saved map.

Request body: none.

Curl:

```bash
curl http://localhost:8080/api/maps/my_room_map
```

Response:

```json
{
  "map_id": "my_room_map",
  "name": "My Room",
  "resolution": 0.05,
  "origin": {
    "x": 0.0,
    "y": 0.0
  },
  "width": 99,
  "height": 99,
  "occupancy": [0, 0, 100]
}
```

`occupancy` is the full occupancy-grid array and can be large. Unknown
`map_id` returns HTTP `404` with FastAPI detail text:

```json
{
  "detail": "Map not found"
}
```

### GET /api/maps/{map_id}/metadata

Returns metadata for one saved map without the occupancy array.

Request body: none.

Curl:

```bash
curl http://localhost:8080/api/maps/my_room_map/metadata
```

Response:

```json
{
  "map_id": "my_room_map",
  "name": "My Room",
  "created_at": "2026-06-23T00:00:00+05:30",
  "updated_at": "2026-06-23T16:36:13.499284",
  "width": 99,
  "height": 99,
  "resolution": 0.05,
  "sections": [
    {
      "section_id": "sec_001",
      "name": "Left side",
      "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    }
  ]
}
```

Unknown `map_id` returns HTTP `404`.

### PUT /api/maps/{map_id}/metadata

Updates a saved map's editable metadata. The current app sends the map name and
section list.

Request body:

```json
{
  "name": "Bedroom",
  "sections": [
    {
      "section_id": "sec_001",
      "name": "Left side",
      "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    }
  ]
}
```

Fields:

| Field | Required | Notes |
|---|---:|---|
| `name` | no | If omitted, the stored name is unchanged. |
| `sections` | no | Replaces the stored section list. Defaults to an empty list. |

Curl:

```bash
curl -X PUT http://localhost:8080/api/maps/my_room_map/metadata \
  -H "Content-Type: application/json" \
  -d '{"name":"Bedroom","sections":[{"section_id":"sec_001","name":"Left side","polygon":[[0,0],[1,0],[1,1],[0,1]]}]}'
```

Response:

```json
{
  "map_id": "my_room_map",
  "name": "Bedroom",
  "created_at": "2026-06-23T00:00:00+05:30",
  "updated_at": "2026-06-24T12:00:00.000000",
  "width": 99,
  "height": 99,
  "resolution": 0.05,
  "sections": [
    {
      "section_id": "sec_001",
      "name": "Left side",
      "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]
    }
  ]
}
```

Unknown `map_id` returns HTTP `404`.

### POST /api/cleaning/start

Starts cleaning for a selected saved map. An empty `sections` list means
full-map cleaning in the current app/mock flow. A non-empty list means selected
section cleaning.

Request body for full-map cleaning:

```json
{
  "map_id": "my_room_map",
  "sections": []
}
```

Request body for selected-section cleaning:

```json
{
  "map_id": "my_room_map",
  "sections": [
    {
      "section_id": "sec_001",
      "name": "Left side",
      "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    }
  ]
}
```

Fields:

| Field | Required | Notes |
|---|---:|---|
| `map_id` | yes | Must exist in the robot/mock map store. |
| `sections` | no | Defaults to `[]`; the app sends one selected section for section cleaning. |

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{"map_id":"my_room_map","sections":[]}'
```

Accepted response:

```json
{
  "accepted": true,
  "task_id": "task_a1b2c3",
  "state": "cleaning",
  "map_id": "my_room_map",
  "sections": [],
  "message": "Mock cleaning started"
}
```

Rejected response for an unknown map:

```json
{
  "accepted": false,
  "message": "Map not found"
}
```

### POST /api/cleaning/pause

Pauses an active cleaning task.

Request body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/pause
```

Accepted response:

```json
{
  "accepted": true,
  "state": "paused"
}
```

Rejected response when the robot is not cleaning:

```json
{
  "accepted": false,
  "message": "Robot is not cleaning"
}
```

### POST /api/cleaning/resume

Resumes a paused cleaning task.

Request body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/resume
```

Accepted response:

```json
{
  "accepted": true,
  "state": "cleaning"
}
```

Rejected response when the robot is not paused:

```json
{
  "accepted": false,
  "message": "Robot is not paused"
}
```

### POST /api/cleaning/stop

Stops cleaning and clears the current mock cleaning state.

Request body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/stop
```

Response:

```json
{
  "accepted": true,
  "state": "idle",
  "message": "Mock cleaning stopped"
}
```

## Current Endpoint Summary

```text
GET  /api/robot/status

POST /api/exploration/start
GET  /api/exploration/status
POST /api/exploration/manual-drive
POST /api/exploration/stop

GET  /api/maps
GET  /api/maps/{map_id}
GET  /api/maps/{map_id}/metadata
PUT  /api/maps/{map_id}/metadata

POST /api/cleaning/start
POST /api/cleaning/pause
POST /api/cleaning/resume
POST /api/cleaning/stop
```
