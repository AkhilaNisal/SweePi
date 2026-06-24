# SweePi API Bridge Guide

The SweePi API bridge exposes the robot stack to HTTP clients such as the
Flutter mobile app, `curl`, and Postman.

This document is focused only on the endpoints needed for mobile app
integration.

```text
HTTP base URL: http://<robot-ip>:8080
API prefix:    /api
```

Example local URL while testing on the robot computer:

```text
http://localhost:8080/api/robot/status
```

Implementation location:

```text
src/raspberry_pi/src/sweepi_api_bridge/sweepi_api_bridge/api_bridge_node.py
```

## Important API Decisions

1. **No API version prefix for now.**

   Use:

   ```text
   /api/robot/status
   /api/maps
   /api/exploration/start
   ```

   Do not use:

   ```text
   /api/v1/robot/status
   /api/v1/maps
   /api/v1/exploration/start
   ```

2. **The robot is the source of truth for maps.**

   The mobile app does not own the map files. During exploration, the app sends
   the map name to the robot. The robot stores the map with a generated
   `map_id`. Later, the app fetches map metadata and the map data from the
   robot.

3. **Map versions and map revisions are not part of this API for now.**

   The app should select maps using `map_id`.

4. **Exploration and cleaning must not run at the same time.**

   If the robot is exploring, cleaning commands should be rejected. If the robot
   is cleaning, exploration commands should be rejected.

5. **Manual exploration mode controls the robot like a remote-control car.**

   Manual movement commands are only accepted while exploration is active and
   the exploration mode is `manual`.

6. **History, schedules, WebSockets, and simulation launch instructions are not
   included in this API.**

## Mobile App Workflow

### 1. Check robot status

```bash
curl http://localhost:8080/api/robot/status
```

### 2. Start exploration

Automatic exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"living_room","mode":"automatic"}'
```

Manual exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"living_room","mode":"manual"}'
```

### 3. During manual exploration, drive the robot

Move forward:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"forward","speed":0.15,"duration_ms":500}'
```

Rotate left:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"rotate_left","speed":0.6,"duration_ms":500}'
```

Stop manual motion:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/stop
```

### 4. Fetch live map while exploring

```bash
curl http://localhost:8080/api/maps/current
```

### 5. Stop exploration and save the map

```bash
curl -X POST http://localhost:8080/api/exploration/stop
```

The robot returns the saved `map_id`.

### 6. Fetch all saved map metadata

```bash
curl http://localhost:8080/api/maps
```

### 7. Fetch a saved map by id

```bash
curl http://localhost:8080/api/maps/map_living_room_20260623_101530
```

### 8. Mobile app divides the map into sections

The mobile app can send the user-defined sections back to the robot:

```bash
curl -X PUT http://localhost:8080/api/maps/map_living_room_20260623_101530/sections \
  -H "Content-Type: application/json" \
  -d '{
    "sections":[
      {
        "section_id":"living_room_left",
        "name":"Living Room Left",
        "polygon":[[0.0,0.0],[2.0,0.0],[2.0,2.0],[0.0,2.0]]
      }
    ],
    "no_go_zones":[]
  }'
```

### 9. Start cleaning using a selected map and sections

Clean selected sections:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_id":"task_living_room_001",
    "map_id":"map_living_room_20260623_101530",
    "cleaning_mode":"sections",
    "section_ids":["living_room_left"],
    "no_go_zones":[]
  }'
```

Clean the full map:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_id":"task_living_room_full_001",
    "map_id":"map_living_room_20260623_101530",
    "cleaning_mode":"full_map"
  }'
```

## Endpoint Reference

All endpoints return JSON.

Malformed JSON or invalid request data should return HTTP `400`.

Unknown paths should return HTTP `404`.

Commands that reach the API bridge but are rejected by the robot state can
return HTTP `200` with `"accepted": false`.

---

# Robot API

## GET /api/robot/status

Purpose: Return the current robot, navigation, map, exploration, and cleaning
state.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/robot/status
```

Expected response:

```json
{
  "robot_id": "sweepi-robot-001",
  "state": "idle",
  "mode": "automatic",
  "battery": {
    "percent": null,
    "charging": null
  },
  "pose": {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "frame": "map"
  },
  "exploration": {
    "active": false,
    "mode": null,
    "area_name": null,
    "map_id": null,
    "map_available": false
  },
  "cleaning": {
    "active": false,
    "task_id": null,
    "type": null,
    "progress_percent": 0.0,
    "map_id": null,
    "section_ids": [],
    "sections": [],
    "no_go_zones": []
  },
  "map": {
    "map_id": null,
    "name": null,
    "available": false
  },
  "nav": {
    "execution_status": "WAITING_FOR_PATH",
    "coverage_stats": ""
  },
  "errors": [],
  "warnings": []
}
```

Notes:

- Keep this endpoint available at all times.
- `pose` is `null` until the bridge can look up the `map -> base_link`
  transform.
- `battery.percent` and `battery.charging` can stay `null` until battery
  telemetry is connected.
- Do not include map revisions or API version fields.

---

# Exploration API

The exploration API keeps the existing exploration behavior but adds an
exploration mode field.

Supported modes:

```text
automatic
manual
```

Use `automatic` when the robot should explore by itself.

Use `manual` when the app should drive the robot manually while the robot maps
the environment.

## POST /api/exploration/start

Purpose: Start a mapping/exploration session and register the map name that
should be saved by the robot.

Required body:

```json
{
  "area_name": "living_room",
  "mode": "automatic"
}
```

Fields:

| Field | Required | Description |
|---|---:|---|
| `area_name` | yes | User-facing map name from the app. Example: `living_room`, `kitchen`, `first_floor`. |
| `mode` | no | `automatic` or `manual`. Default should be `automatic`. |

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"living_room","mode":"automatic"}'
```

Expected response:

```json
{
  "accepted": true,
  "state": "exploring",
  "mode": "automatic",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "message": "Exploration started"
}
```

Manual mode example:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"living_room","mode":"manual"}'
```

Expected response:

```json
{
  "accepted": true,
  "state": "exploring",
  "mode": "manual",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "message": "Manual exploration started"
}
```

Expected rejected response if cleaning is already running:

```json
{
  "accepted": false,
  "state": "cleaning",
  "message": "Cannot start exploration while cleaning is active"
}
```

Implementation notes:

- In `automatic` mode, start the current autonomous exploration behavior.
- In `manual` mode, keep mapping active but do not send autonomous frontier
  goals.
- Generate or reserve a stable `map_id` at the start of exploration.
- Store the mapping session context in the bridge:
  - `area_name`
  - `mode`
  - `map_id`
  - start time

## GET /api/exploration/status

Purpose: Return the latest exploration state cached by the bridge.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/exploration/status
```

Expected automatic-mode response:

```json
{
  "state": "exploring",
  "mode": "automatic",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "map_available": true,
  "frontiers_remaining": 10,
  "last_goal": {
    "x": 1.2,
    "y": 0.5
  },
  "message": "Navigating to frontier"
}
```

Expected manual-mode response:

```json
{
  "state": "exploring",
  "mode": "manual",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "map_available": true,
  "frontiers_remaining": null,
  "last_goal": null,
  "message": "Manual exploration active"
}
```

Reliable fields:

```text
state
mode
area_name
map_id
map_available
frontiers_remaining
last_goal
message
```

## POST /api/exploration/mode

Purpose: Switch between manual and automatic exploration during an active
exploration session.

Required body:

```json
{
  "mode": "manual"
}
```

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"manual"}'
```

Expected response:

```json
{
  "accepted": true,
  "state": "exploring",
  "mode": "manual",
  "message": "Exploration mode changed to manual"
}
```

Expected rejected response if exploration is not active:

```json
{
  "accepted": false,
  "state": "idle",
  "message": "Cannot change exploration mode because exploration is not active"
}
```

Implementation notes:

- Switching from `automatic` to `manual` should cancel the current autonomous
  exploration goal before accepting manual velocity commands.
- Switching from `manual` to `automatic` should stop any current manual velocity
  command before restarting autonomous exploration.

## POST /api/exploration/manual/drive

Purpose: Send a direct velocity command while manual exploration is active.

This endpoint is useful for joystick-style app control.

Required body:

```json
{
  "linear_x": 0.15,
  "angular_z": 0.0,
  "duration_ms": 300
}
```

Fields:

| Field | Required | Unit | Description |
|---|---:|---|---|
| `linear_x` | yes | m/s | Forward/backward velocity. Positive = forward. Negative = backward. |
| `angular_z` | yes | rad/s | Rotation velocity. Positive = rotate left. Negative = rotate right. |
| `duration_ms` | no | ms | Safety timeout for this command. Default can be `300`. Recommended max: `1000`. |

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/drive \
  -H "Content-Type: application/json" \
  -d '{"linear_x":0.15,"angular_z":0.0,"duration_ms":300}'
```

Expected response:

```json
{
  "accepted": true,
  "mode": "manual",
  "command": {
    "linear_x": 0.15,
    "angular_z": 0.0,
    "duration_ms": 300
  },
  "message": "Manual drive command accepted"
}
```

Expected rejected response if not in manual exploration mode:

```json
{
  "accepted": false,
  "state": "exploring",
  "mode": "automatic",
  "message": "Manual drive commands require exploration mode=manual"
}
```

Implementation notes:

- Publish to the robot velocity topic, for example `/cmd_vel`.
- Apply a safety timeout. If no new manual command arrives before the timeout,
  publish zero velocity.
- Clamp velocities to safe robot limits in the bridge.
- Recommended app behavior: send commands repeatedly while the user holds a
  button or joystick, then call `/api/exploration/manual/stop` when released.

## POST /api/exploration/manual/command

Purpose: Send a simple button-style manual command.

This endpoint is easier for a mobile app with buttons such as forward,
backward, rotate left, rotate right, and stop.

Required body:

```json
{
  "command": "forward",
  "speed": 0.15,
  "duration_ms": 500
}
```

Supported `command` values:

```text
forward
backward
rotate_left
rotate_right
stop
```

Curl examples:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"forward","speed":0.15,"duration_ms":500}'
```

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"backward","speed":0.15,"duration_ms":500}'
```

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"rotate_left","speed":0.6,"duration_ms":500}'
```

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H "Content-Type: application/json" \
  -d '{"command":"rotate_right","speed":0.6,"duration_ms":500}'
```

Expected response:

```json
{
  "accepted": true,
  "mode": "manual",
  "command": "forward",
  "message": "Manual command accepted"
}
```

Implementation mapping:

| Command | Velocity mapping |
|---|---|
| `forward` | `linear_x = +speed`, `angular_z = 0.0` |
| `backward` | `linear_x = -speed`, `angular_z = 0.0` |
| `rotate_left` | `linear_x = 0.0`, `angular_z = +speed` |
| `rotate_right` | `linear_x = 0.0`, `angular_z = -speed` |
| `stop` | `linear_x = 0.0`, `angular_z = 0.0` |

## POST /api/exploration/manual/stop

Purpose: Stop manual robot motion immediately.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/stop
```

Expected response:

```json
{
  "accepted": true,
  "mode": "manual",
  "message": "Manual motion stopped"
}
```

Implementation notes:

- Publish zero velocity immediately.
- This endpoint should be safe to call repeatedly.

## POST /api/exploration/stop

Purpose: Stop exploration and save the current live map on the robot using the
`area_name` and `map_id` from `/api/exploration/start`.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/exploration/stop
```

Expected response when the live map is available:

```json
{
  "accepted": true,
  "state": "idle",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "map_saved": true,
  "message": "Exploration stopped and map saved"
}
```

Expected response when no live map is available:

```json
{
  "accepted": true,
  "state": "idle",
  "area_name": "living_room",
  "map_id": "map_living_room_20260623_101530",
  "map_saved": false,
  "message": "Exploration stopped, but no live /map was available to save"
}
```

Implementation notes:

- Stop autonomous exploration if it is running.
- Stop manual motion if the mode is `manual`.
- Save the current map to the robot map store.
- Save metadata containing at least:
  - `map_id`
  - `name`
  - `created_at`
  - `updated_at`
  - `resolution`
  - `width`
  - `height`
  - `origin`
  - `sections`
  - `no_go_zones`
  - `labels`

---

# Maps API

The robot is the source of truth for saved maps.

The app should use:

```text
GET /api/maps
```

to list map metadata, and:

```text
GET /api/maps/{map_id}
```

to fetch the actual map data.

## GET /api/maps/current

Purpose: Get the current live map while exploration or mapping is active.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/maps/current
```

Expected response before `/map` is available:

```json
{
  "available": false,
  "map_id": null,
  "name": null,
  "robot_pose": null
}
```

Expected response after `/map` is available:

```json
{
  "available": true,
  "map_id": "map_living_room_20260623_101530",
  "name": "living_room",
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "width": 400,
  "height": 400,
  "occupancy": [0, 0, 100],
  "robot_pose": {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "frame": "map"
  }
}
```

Notes:

- `occupancy` is the full occupancy-grid array and can be large.
- This endpoint is mainly for live exploration UI.
- Do not include map revision fields.

## GET /api/maps

Purpose: Return metadata for all maps currently stored on the robot.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/maps
```

Expected response:

```json
{
  "items": [
    {
      "map_id": "map_living_room_20260623_101530",
      "name": "living_room",
      "created_at": "2026-06-23T10:15:30+05:30",
      "updated_at": "2026-06-23T10:20:00+05:30",
      "resolution": 0.05,
      "origin": {
        "x": -10.0,
        "y": -10.0,
        "yaw": 0.0
      },
      "width": 400,
      "height": 400,
      "sections": [
        {
          "section_id": "living_room_left",
          "name": "Living Room Left",
          "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
        }
      ],
      "no_go_zones": [],
      "labels": []
    }
  ]
}
```

Implementation notes:

- Do not expose robot filesystem paths to the mobile app unless needed for
  debugging.
- Return metadata only. Do not include the full occupancy array in this list
  endpoint.

## GET /api/maps/{map_id}

Purpose: Fetch a saved map from the robot by `map_id`.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/maps/map_living_room_20260623_101530
```

Expected response:

```json
{
  "map_id": "map_living_room_20260623_101530",
  "name": "living_room",
  "created_at": "2026-06-23T10:15:30+05:30",
  "updated_at": "2026-06-23T10:20:00+05:30",
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "width": 400,
  "height": 400,
  "occupancy": [0, 0, 100],
  "sections": [
    {
      "section_id": "living_room_left",
      "name": "Living Room Left",
      "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    }
  ],
  "no_go_zones": [],
  "labels": []
}
```

Expected response if the map does not exist:

```json
{
  "error": "Map not found",
  "map_id": "map_living_room_20260623_101530"
}
```

## GET /api/maps/{map_id}/metadata

Purpose: Fetch metadata for one saved map without returning the full occupancy
array.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/maps/map_living_room_20260623_101530/metadata
```

Expected response:

```json
{
  "map_id": "map_living_room_20260623_101530",
  "name": "living_room",
  "created_at": "2026-06-23T10:15:30+05:30",
  "updated_at": "2026-06-23T10:20:00+05:30",
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "width": 400,
  "height": 400,
  "sections": [],
  "no_go_zones": [],
  "labels": []
}
```

## PUT /api/maps/{map_id}/sections

Purpose: Save app-defined map sections on the robot.

The mobile app performs section creation. The robot stores the section metadata
so the app can fetch it later and so cleaning can reference section ids.

Required body:

```json
{
  "sections": [
    {
      "section_id": "living_room_left",
      "name": "Living Room Left",
      "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    }
  ],
  "no_go_zones": []
}
```

Curl:

```bash
curl -X PUT http://localhost:8080/api/maps/map_living_room_20260623_101530/sections \
  -H "Content-Type: application/json" \
  -d '{
    "sections":[
      {
        "section_id":"living_room_left",
        "name":"Living Room Left",
        "polygon":[[0.0,0.0],[2.0,0.0],[2.0,2.0],[0.0,2.0]]
      }
    ],
    "no_go_zones":[]
  }'
```

Expected response:

```json
{
  "accepted": true,
  "map_id": "map_living_room_20260623_101530",
  "sections": [
    {
      "section_id": "living_room_left",
      "name": "Living Room Left",
      "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    }
  ],
  "no_go_zones": [],
  "message": "Map sections updated"
}
```

Validation rules:

- `sections` must be a list.
- Each `section_id` must be unique within the map.
- Each polygon must contain at least three `[x, y]` points.
- `no_go_zones` follows the same polygon rules.
- Coordinates are in the map frame.

Implementation notes:

- This endpoint replaces the old room/zone metadata workflow for now.
- The mobile app can still divide the map however it wants; the robot only
  stores and later uses the polygons.

---

# Cleaning API

The cleaning API must always receive the target `map_id`.

The app can start:

1. full-map cleaning, or
2. selected-section cleaning.

The old separate selected-cleaning flow is not required for the current app
integration. Use one start endpoint:

```text
POST /api/cleaning/start
```

## POST /api/cleaning/start

Purpose: Start cleaning using a selected saved map.

Required body for full-map cleaning:

```json
{
  "task_id": "task_living_room_full_001",
  "map_id": "map_living_room_20260623_101530",
  "cleaning_mode": "full_map"
}
```

Required body for selected-section cleaning:

```json
{
  "task_id": "task_living_room_sections_001",
  "map_id": "map_living_room_20260623_101530",
  "cleaning_mode": "sections",
  "section_ids": ["living_room_left"],
  "no_go_zones": []
}
```

Alternative selected-section body with inline polygons:

```json
{
  "task_id": "task_living_room_sections_001",
  "map_id": "map_living_room_20260623_101530",
  "cleaning_mode": "sections",
  "sections": [
    {
      "section_id": "custom_section_1",
      "name": "Custom Section 1",
      "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    }
  ],
  "no_go_zones": []
}
```

Fields:

| Field | Required | Description |
|---|---:|---|
| `task_id` | no | App-generated task id. If omitted, the bridge can generate one. |
| `map_id` | yes | Saved robot map id to clean. |
| `cleaning_mode` | no | `full_map` or `sections`. Default can be `full_map`. |
| `section_ids` | no | Section ids saved under the selected map. Used when `cleaning_mode=sections`. |
| `sections` | no | Inline section polygons from the app. Used when the app does not want to pre-save sections. |
| `no_go_zones` | no | Extra no-go polygons for this cleaning task. |

Curl for full-map cleaning:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_id":"task_living_room_full_001",
    "map_id":"map_living_room_20260623_101530",
    "cleaning_mode":"full_map"
  }'
```

Curl for selected-section cleaning:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_id":"task_living_room_sections_001",
    "map_id":"map_living_room_20260623_101530",
    "cleaning_mode":"sections",
    "section_ids":["living_room_left"],
    "no_go_zones":[]
  }'
```

Expected accepted response:

```json
{
  "accepted": true,
  "task_id": "task_living_room_sections_001",
  "state": "cleaning",
  "map_id": "map_living_room_20260623_101530",
  "cleaning_mode": "sections",
  "section_ids": ["living_room_left"],
  "message": "Cleaning started"
}
```

Expected rejected response if the map does not exist:

```json
{
  "accepted": false,
  "message": "Cannot start cleaning because map_id was not found",
  "map_id": "map_living_room_20260623_101530"
}
```

Expected rejected response if exploration is active:

```json
{
  "accepted": false,
  "state": "exploring",
  "message": "Cannot start cleaning while exploration is active"
}
```

Expected rejected response if selected cleaning has no valid section:

```json
{
  "accepted": false,
  "message": "Selected-section cleaning requires at least one section_id or inline section polygon"
}
```

Implementation notes:

- Before starting coverage, load or activate the selected saved map for the
  robot navigation stack if the current active map is different.
- Resolve `section_ids` using metadata stored under the selected `map_id`.
- Publish selected section polygons and no-go zones to the coverage system.
- Then call the existing coverage manager start service.
- Keep only one cleaning task active at a time.

## POST /api/cleaning/pause

Purpose: Pause the active cleaning task.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/pause
```

Expected response:

```json
{
  "accepted": true,
  "state": "paused",
  "message": "Cleaning paused"
}
```

Expected rejected response:

```json
{
  "accepted": false,
  "state": "idle",
  "message": "Cannot pause cleaning while state=idle"
}
```

## POST /api/cleaning/resume

Purpose: Resume a paused cleaning task.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/resume
```

Expected response:

```json
{
  "accepted": true,
  "state": "cleaning",
  "message": "Cleaning resumed"
}
```

Expected rejected response:

```json
{
  "accepted": false,
  "state": "idle",
  "message": "Cannot resume cleaning while state=idle"
}
```

## POST /api/cleaning/stop

Purpose: Stop or cancel the active cleaning task.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/cleaning/stop
```

Expected response:

```json
{
  "accepted": true,
  "state": "idle",
  "message": "Cleaning stopped"
}
```

Expected rejected response:

```json
{
  "accepted": false,
  "state": "idle",
  "message": "Cannot stop cleaning while state=idle"
}
```

---

# Removed From Current API Scope

The following items are intentionally removed from this app-integration API
document for now:

```text
/api/v1/* versioned paths
GET /api/history
GET /api/schedules
POST /api/schedules
PUT /api/schedules/{schedule_id}
DELETE /api/schedules/{schedule_id}
WebSocket status stream
Run simulation instructions
Map revision / map version fields
Standalone map save endpoint for the app
Standalone map load endpoint for the app
```

Map save now happens through:

```text
POST /api/exploration/stop
```

Map selection for cleaning now happens through:

```text
POST /api/cleaning/start
```

---

# Postman Basics

For HTTP requests:

1. Create a new HTTP request.
2. Set the method and URL from this document.
3. For endpoints with a JSON body, choose `Body` -> `raw` -> `JSON`.
4. Add header:

   ```text
   Content-Type: application/json
   ```

5. Click `Send`.

---

# Implementation Checklist

Use this checklist when updating `api_bridge_node.py`.

## Routing

Add or update routes:

```text
GET  /api/robot/status

POST /api/exploration/start
GET  /api/exploration/status
POST /api/exploration/mode
POST /api/exploration/manual/drive
POST /api/exploration/manual/command
POST /api/exploration/manual/stop
POST /api/exploration/stop

GET  /api/maps/current
GET  /api/maps
GET  /api/maps/{map_id}
GET  /api/maps/{map_id}/metadata
PUT  /api/maps/{map_id}/sections

POST /api/cleaning/start
POST /api/cleaning/pause
POST /api/cleaning/resume
POST /api/cleaning/stop
```

Remove or ignore app-facing routes:

```text
/api/v1/*
/api/history
/api/schedules*
WebSocket endpoints
```

## State Rules

- `idle -> exploration/start` is allowed.
- `idle -> cleaning/start` is allowed only with a valid `map_id`.
- `exploring -> cleaning/start` is rejected.
- `cleaning -> exploration/start` is rejected.
- Manual drive commands are accepted only when:
  - `state=exploring`
  - `exploration.mode=manual`
- `cleaning/pause` is accepted only when cleaning is active.
- `cleaning/resume` is accepted only when state is `paused`.
- `cleaning/stop` is accepted only when cleaning is active or paused.

## ROS Wiring

Suggested wiring targets:

```text
Manual drive commands       -> /cmd_vel
Automatic exploration start -> existing exploration start service/action
Exploration stop            -> existing exploration stop service/action + map save
Live map                    -> /map
Robot pose                  -> TF map -> base_link
Cleaning start              -> selected map activation + coverage selection publish + manager start
Cleaning pause              -> coverage manager pause
Cleaning resume             -> coverage manager resume
Cleaning stop               -> coverage manager stop
```

## Map Storage

For each saved map, store:

```text
map_id
name
created_at
updated_at
resolution
origin
width
height
occupancy or map file reference
sections
no_go_zones
labels
```

The app should not need to know robot filesystem paths.

## Safety

Manual mode should always be timeout-based.

Recommended behavior:

- On every manual command, publish the requested velocity.
- Store command expiry time.
- If the command expires and no new command arrived, publish zero velocity.
- When switching out of manual mode, publish zero velocity.
- When stopping exploration, publish zero velocity.
- Clamp maximum linear and angular speed in the bridge.

