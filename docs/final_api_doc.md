# SweePi Unified API Contract

This document is the single source of truth for communication between the SweePi mobile app, development mock server, and real robot API bridge.

The API must be implemented consistently in:

* Flutter mobile app API client
* Development mock API server
* Real robot API bridge on the robot branch

The old ROS API bridge inside the `app-rpi-integration` branch is ignored for this contract. It must not be used as a reference for the final API shape.

---

## 1. Base URL

Default robot API base URL:

```text
http://<robot-ip>:8080/api
```

Example for local mock server:

```text
http://localhost:8080/api
```

All endpoints in this document are relative to `/api`.

---

## 2. General API Rules

### 2.1 Response Format

All responses should follow one consistent structure.

The response should include these common top-level fields:

```json
{
  "success": true,
  "message": "Human readable message.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z"
}
```

Endpoint-specific data should also be returned at the top level.

Do **not** wrap endpoint data inside a `data` object, because the current Flutter app expects fields such as `items`, `state`, `task_id`, `map_id`, and `sections` directly at the top level.

Example successful response:

```json
{
  "success": true,
  "message": "Coverage validation completed successfully.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "command": "validate_cleaning",
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "task_id": "cleaning_20260624_001",
  "state": "coverage_validated",
  "map_id": "my_room"
}
```

Example error response:

```json
{
  "success": false,
  "message": "initial_pose is required.",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "field": "initial_pose"
    }
  },
  "timestamp": "2026-06-24T12:00:00Z"
}
```

---

### 2.2 Command Lifecycle Fields

Robot command endpoints must include top-level command lifecycle fields:

| Field | Meaning |
| --- | --- |
| `accepted` | The API bridge accepted the command and attempted the ROS/mock action. |
| `completed` | This endpoint's immediate command step reached its confirmation condition. |
| `task_finished` | The whole long-running task is finished. Start commands normally return `false`. |
| `task_result` | Final task result such as `completed`, `stopped`, `reset`, `failed`, or `map_saved`. |
| `state` | Current robot/task state or next state. |
| `command` | Stable command name for app logic. |
| `next_steps` | Optional ordered hints for the next API calls. |
| `error` | Structured error object when `success=false`. |

`accepted=true` does not mean the robot task succeeded. It means the bridge
accepted the request and tried to send or publish it. `completed=true` means the
specific command step completed, for example initial pose was confirmed by
localization instead of only published to `/initialpose`.

Long-running tasks such as cleaning, exploration, and return-home require
status polling for the final result. The mobile app must not proceed to the next
cleaning step unless the previous command response has both `success=true` and
`completed=true`.

Cleaning command sequence:

```text
POST /api/cleaning/start
  -> waiting_for_initial_pose

POST /api/localization/initial-pose
  -> initial_pose_confirmed or initial_pose_failed

POST /api/cleaning/validate
  -> coverage_validated or coverage_validation_failed

POST /api/cleaning/start-motion
  -> cleaning or cleaning_start_failed

GET /api/cleaning/status
  -> running/completed/failed/progress
```

See also [`docs/command_lifecycle.md`](command_lifecycle.md).

---

## 3. Common Data Types

### 3.1 Pose

Used for robot pose and initial pose.

```json
{
  "x": 0.0,
  "y": 0.0,
  "yaw": 0.0,
  "frame": "map"
}
```

Fields:

| Field   | Type   | Required | Description                      |
| ------- | ------ | -------: | -------------------------------- |
| `x`     | number |      yes | X position in meters             |
| `y`     | number |      yes | Y position in meters             |
| `yaw`   | number |      yes | Robot yaw angle in radians       |
| `frame` | string |       no | Coordinate frame. Default: `map` |

---

### 3.2 Map Origin

```json
{
  "x": -10.0,
  "y": -10.0,
  "yaw": 0.0
}
```

---

### 3.3 Section

A section is a small rectangular area inside a map.

Sections are selected by the mobile app. A cleaning request can include one or more sections.

```json
{
  "section_id": "section_1",
  "name": "Section 1",
  "bounds": {
    "x": 1.2,
    "y": 0.8,
    "width": 2.0,
    "height": 1.5
  }
}
```

Fields:

| Field           | Type   | Required | Description                                |
| --------------- | ------ | -------: | ------------------------------------------ |
| `section_id`    | string |      yes | Unique section ID                          |
| `name`          | string |       no | Human-readable section name                |
| `bounds.x`      | number |      yes | Rectangle start X in map/world coordinates |
| `bounds.y`      | number |      yes | Rectangle start Y in map/world coordinates |
| `bounds.width`  | number |      yes | Rectangle width                            |
| `bounds.height` | number |      yes | Rectangle height                           |

The app may also send processed map data for the selected sections through `processed_map`.

---

### 3.4 Processed Map

The `processed_map` object represents the map after the app applies selected section boundaries or masks.

This field is used when the app creates a black bounded selected cleaning area before sending the robot.

```json
{
  "width": 384,
  "height": 384,
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "occupancy": [0, 0, 100, -1]
}
```

Fields:

| Field        | Type              | Required | Description         |
| ------------ | ----------------- | -------: | ------------------- |
| `width`      | integer           |      yes | Map width in cells  |
| `height`     | integer           |      yes | Map height in cells |
| `resolution` | number            |      yes | Meters per cell     |
| `origin`     | object            |      yes | Map origin          |
| `occupancy`  | array of integers |      yes | Occupancy grid data |

Occupancy values:

| Value | Meaning  |
| ----: | -------- |
|   `0` | Free     |
| `100` | Occupied |
|  `-1` | Unknown  |

---

## 4. System Endpoints

---

### 4.1 Health Check

```http
GET /api/system/health
```

Checks whether the API server is running.

#### Response

```json
{
  "success": true,
  "message": "API server is healthy.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "status": "ok",
  "robot_connected": true,
  "server": "sweepi_api_bridge"
}
```

---

## 5. Robot Endpoints

---

### 5.1 Get Robot Status

```http
GET /api/robot/status
```

Returns the current robot state.

#### Response

```json
{
  "success": true,
  "message": "Robot status fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "robot_id": "sweepi-robot-001",
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
    "map_id": "my_room",
    "name": "My Room"
  },
  "cleaning": {
    "active": false,
    "task_id": null,
    "map_id": null,
    "cleaning_mode": null,
    "progress_percent": 0.0
  },
  "exploration": {
    "active": false,
    "map_name": null,
    "mode": null
  },
  "nav": {
    "execution_status": "IDLE"
  },
  "errors": [],
  "warnings": []
}
```

Recommended robot `state` values:

| State            | Meaning                    |
| ---------------- | -------------------------- |
| `idle`           | Robot is not doing a task  |
| `exploring`      | Robot is mapping/exploring |
| `cleaning`       | Robot is cleaning          |
| `paused`         | Current task is paused     |
| `returning_home` | Robot is returning home    |
| `error`          | Robot has an error         |

---

## 6. Map Endpoints

---

### 6.1 List Maps

```http
GET /api/maps
```

Returns available saved maps.

This endpoint must keep the top-level `items` field because the Flutter app expects this structure.

#### Response

```json
{
  "success": true,
  "message": "Maps fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "items": [
    {
      "map_id": "my_room",
      "name": "My Room",
      "created_at": "2026-06-24T10:00:00Z",
      "updated_at": "2026-06-24T10:30:00Z",
      "resolution": 0.05,
      "origin": {
        "x": -10.0,
        "y": -10.0,
        "yaw": 0.0
      },
      "width": 384,
      "height": 384,
      "sections": [
        {
          "section_id": "section_1",
          "name": "Section 1",
          "bounds": {
            "x": 1.2,
            "y": 0.8,
            "width": 2.0,
            "height": 1.5
          }
        }
      ]
    }
  ]
}
```

---

### 6.2 Get Map

```http
GET /api/maps/{map_id}
```

Returns full map data, including occupancy grid.

#### Response

```json
{
  "success": true,
  "message": "Map fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "map_id": "my_room",
  "name": "My Room",
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "width": 384,
  "height": 384,
  "occupancy": [0, 0, 0, 100, -1],
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    }
  ]
}
```

---

### 6.3 Get Map Metadata

```http
GET /api/maps/{map_id}/metadata
```

Returns map metadata without full occupancy data.

#### Response

```json
{
  "success": true,
  "message": "Map metadata fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "map_id": "my_room",
  "name": "My Room",
  "created_at": "2026-06-24T10:00:00Z",
  "updated_at": "2026-06-24T10:30:00Z",
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0,
    "yaw": 0.0
  },
  "width": 384,
  "height": 384,
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    }
  ]
}
```

---

### 6.4 Update Map Metadata

```http
PUT /api/maps/{map_id}/metadata
```

Updates map name and sections.

#### Request Body

```json
{
  "name": "My Room",
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    },
    {
      "section_id": "section_2",
      "name": "Section 2",
      "bounds": {
        "x": 3.5,
        "y": 1.0,
        "width": 1.8,
        "height": 1.2
      }
    }
  ]
}
```

#### Response

```json
{
  "success": true,
  "message": "Map metadata updated.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "map_id": "my_room",
  "name": "My Room",
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    },
    {
      "section_id": "section_2",
      "name": "Section 2",
      "bounds": {
        "x": 3.5,
        "y": 1.0,
        "width": 1.8,
        "height": 1.2
      }
    }
  ]
}
```

---

## 7. Exploration Endpoints

---

### 7.1 Start Exploration

```http
POST /api/exploration/start
```

Starts exploration/mapping.

The request must use `map_name`.

Do not use `area_name`.

#### Request Body

```json
{
  "map_name": "my_room",
  "mode": "automatic"
}
```

Fields:

| Field      | Type   | Required | Description                      |
| ---------- | ------ | -------: | -------------------------------- |
| `map_name` | string |      yes | Name to save the explored map as |
| `mode`     | string |      yes | `automatic` or `manual`          |

Allowed `mode` values:

```text
automatic
manual
```

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Exploration started.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "exploring",
  "map_name": "my_room",
  "mode": "automatic"
}
```

---

### 7.2 Get Exploration Status

```http
GET /api/exploration/status
```

#### Response

```json
{
  "success": true,
  "message": "Exploration status fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "active": true,
  "state": "exploring",
  "map_name": "my_room",
  "mode": "automatic",
  "progress_percent": null,
  "pose": {
    "x": 0.5,
    "y": 0.2,
    "yaw": 1.57,
    "frame": "map"
  },
  "map_available": true
}
```

---

### 7.3 Switch Exploration Mode

```http
POST /api/exploration/switch
```

Switches the robot between automatic and manual mode during an active exploration.

#### Request Body

```json
{
  "new_mode": "manual"
}
```

Fields:

| Field      | Type   | Required | Description             |
| ---------- | ------ | -------: | ----------------------- |
| `new_mode` | string |      yes | `automatic` or `manual` |

Allowed `new_mode` values:

```text
automatic
manual
```

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Exploration mode switched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "exploring",
  "mode": "manual"
}
```

---

### 7.4 Manual Drive During Exploration

```http
POST /api/exploration/manual-drive
```

Sends a manual movement command while exploration is in manual mode.

This endpoint name must stay exactly as `/api/exploration/manual-drive`.

#### Request Body

```json
{
  "command": "forward",
  "speed": 0.2
}
```

Allowed `command` values:

| Command    | Meaning       |
| ---------- | ------------- |
| `forward`  | Move forward  |
| `backward` | Move backward |
| `left`     | Rotate left   |
| `right`    | Rotate right  |
| `stop`     | Stop movement |

Fields:

| Field     | Type   | Required | Description                                     |
| --------- | ------ | -------: | ----------------------------------------------- |
| `command` | string |      yes | Manual command                                  |
| `speed`   | number |       no | Movement speed. Default decided by robot bridge |

#### Response

```json
{
  "success": true,
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "message": "Manual drive command published.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "command": "manual_drive",
  "direction": "forward",
  "speed": 0.2,
  "state": "exploring",
  "verified_motion": false
}
```

---

### 7.5 Stop Exploration

```http
POST /api/exploration/stop
```

Stops exploration and saves the map using the original `map_name`.

#### Request Body

```json
{
  "save_map": true
}
```

Fields:

| Field      | Type    | Required | Description                              |
| ---------- | ------- | -------: | ---------------------------------------- |
| `save_map` | boolean |       no | Whether to save the map. Default: `true` |

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Exploration stopped and map saved.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "idle",
  "map_saved": true,
  "map_id": "my_room",
  "map_name": "my_room"
}
```

---

## 8. Cleaning Endpoints

---

### 8.1 Start Cleaning

```http
POST /api/cleaning/start
```

Prepares a cleaning task.

The robot must not move from this endpoint. After this call, the API bridge
launches coverage and waits for an initial pose from either the mobile app or
RViz. The app must then call validation and start-motion as separate steps.

The request must include `cleaning_mode`.

Allowed `cleaning_mode` values:

```text
full-map
sections
```

Rules:

1. `cleaning_mode` is mandatory.
2. `initial_pose` must not be sent in this request.
3. If `cleaning_mode` is `full-map`, `sections` may be empty or omitted.
4. If `cleaning_mode` is `sections`, `sections` is mandatory and must contain at least one section.
5. If `cleaning_mode` is `sections`, more than one section is allowed.
6. If `processed_map` is provided, the robot bridge should use it as the selected-section bounded map.
7. After this call, set initial pose with `POST /api/localization/initial-pose` or RViz `2D Pose Estimate`.
8. Then call `POST /api/cleaning/validate`.
9. Then call `POST /api/cleaning/start-motion`.

---

#### Full Map Cleaning Request

```json
{
  "map_id": "my_room",
  "cleaning_mode": "full-map",
  "sections": []
}
```

---

#### Section Cleaning Request

```json
{
  "map_id": "my_room",
  "cleaning_mode": "sections",
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    },
    {
      "section_id": "section_2",
      "name": "Section 2",
      "bounds": {
        "x": 3.5,
        "y": 1.0,
        "width": 1.8,
        "height": 1.2
      }
    }
  ],
  "processed_map": {
    "width": 384,
    "height": 384,
    "resolution": 0.05,
    "origin": {
      "x": -10.0,
      "y": -10.0,
      "yaw": 0.0
    },
    "occupancy": [0, 0, 0, 100, -1]
  }
}
```

---

#### Successful Response

```json
{
  "success": true,
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "command": "prepare_cleaning",
  "message": "Coverage prepared. Waiting for initial pose from mobile app or RViz.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "task_id": "cleaning_20260624_001",
  "state": "waiting_for_initial_pose",
  "map_id": "my_room",
  "cleaning_mode": "sections",
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1",
      "bounds": {
        "x": 1.2,
        "y": 0.8,
        "width": 2.0,
        "height": 1.5
      }
    },
    {
      "section_id": "section_2",
      "name": "Section 2",
      "bounds": {
        "x": 3.5,
        "y": 1.0,
        "width": 1.8,
        "height": 1.2
      }
    }
  ],
  "initial_pose": null,
  "initial_pose_required": true,
  "progress_percent": 0.0,
  "next_steps": [
    "Set initial pose from RViz or POST /api/localization/initial-pose.",
    "Call POST /api/cleaning/validate.",
    "Call POST /api/cleaning/start-motion."
  ]
}
```

---

#### Error: Initial Pose Sent Too Early

```json
{
  "success": false,
  "accepted": false,
  "completed": false,
  "task_finished": false,
  "command": "prepare_cleaning",
  "message": "initial_pose must be sent separately after cleaning/start.",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "field": "initial_pose",
      "use_endpoint": "/api/localization/initial-pose"
    }
  },
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "invalid_request"
}
```

---

#### Error: Missing Sections for Section Cleaning

```json
{
  "success": false,
  "accepted": false,
  "completed": false,
  "task_finished": false,
  "command": "prepare_cleaning",
  "message": "sections must contain at least one section when cleaning_mode is sections.",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "field": "sections",
      "cleaning_mode": "sections"
    }
  },
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "invalid_request"
}
```

---

#### Error: Invalid Cleaning Mode

```json
{
  "success": false,
  "accepted": false,
  "completed": false,
  "task_finished": false,
  "command": "prepare_cleaning",
  "message": "Invalid cleaning_mode. Allowed values are full-map and sections.",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "field": "cleaning_mode",
      "allowed_values": ["full-map", "sections"]
    }
  },
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "invalid_request"
}
```

---

### 8.2 Set Cleaning Initial Pose

```http
POST /api/localization/initial-pose
```

Sets the initial pose after `POST /api/cleaning/start`. The bridge validates
the pose against the active coverage map when possible, publishes
`/initialpose`, then waits for localization confirmation. The pose may also be
set from RViz with `2D Pose Estimate`.

#### Request Body

```json
{
  "map_id": "my_room",
  "x": 0.0,
  "y": 0.0,
  "yaw": 0.0,
  "frame": "map"
}
```

#### Response

```json
{
  "success": true,
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "command": "set_initial_pose",
  "message": "Initial pose confirmed.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "initial_pose_confirmed",
  "initial_pose_received": true,
  "initial_pose_confirmed": true,
  "initial_pose_source": "api",
  "initial_pose": {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "frame": "map"
  },
  "next_steps": [
    "Call POST /api/cleaning/validate.",
    "Call POST /api/cleaning/start-motion after validation completes."
  ]
}
```

If `/initialpose` was published but localization/TF was not confirmed, the
response is a failed command step:

```json
{
  "success": false,
  "accepted": true,
  "completed": false,
  "task_finished": false,
  "command": "set_initial_pose",
  "message": "Initial pose was published, but localization was not confirmed.",
  "error": {
    "code": "INITIAL_POSE_NOT_CONFIRMED",
    "details": {
      "reason": "map -> base_link TF was not available before timeout"
    }
  },
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "initial_pose_failed",
  "initial_pose_received": true,
  "initial_pose_confirmed": false
}
```

---

### 8.3 Validate Cleaning Path

```http
POST /api/cleaning/validate
```

Requests validation after the initial pose is confirmed and robot pose/TF is
available.

#### Response

```json
{
  "success": true,
  "message": "Coverage validation completed successfully.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "command": "validate_cleaning",
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "state": "coverage_validated",
  "task_id": "cleaning_20260624_001",
  "map_id": "my_room",
  "coverage_map_id": "my_room"
}
```

---

### 8.4 Start Cleaning Motion

```http
POST /api/cleaning/start-motion
```

Starts robot motion after `cleaning/start`, confirmed initial pose, and
successful validation. This endpoint does not auto-validate.

#### Response

```json
{
  "success": true,
  "message": "Cleaning motion started.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "command": "start_cleaning_motion",
  "accepted": true,
  "completed": true,
  "task_finished": false,
  "state": "cleaning",
  "task_id": "cleaning_20260624_001",
  "map_id": "my_room",
  "coverage_map_id": "my_room"
}
```

If validation has not completed for the current coverage path:

```json
{
  "success": false,
  "message": "Coverage validation is required before starting motion.",
  "error": {
    "code": "VALIDATION_REQUIRED",
    "details": {}
  },
  "timestamp": "2026-06-24T12:00:00Z",
  "command": "start_cleaning_motion",
  "accepted": false,
  "completed": false,
  "task_finished": false,
  "state": "validation_required"
}
```

---

### 8.5 Get Cleaning Status

```http
GET /api/cleaning/status
```

Returns current cleaning progress.

#### Response

```json
{
  "success": true,
  "message": "Cleaning status fetched.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "active": true,
  "state": "cleaning",
  "task_id": "cleaning_20260624_001",
  "map_id": "my_room",
  "coverage_map_id": "my_room",
  "cleaning_mode": "sections",
  "sections": [
    {
      "section_id": "section_1",
      "name": "Section 1"
    },
    {
      "section_id": "section_2",
      "name": "Section 2"
    }
  ],
  "progress_percent": 42.5,
  "pose": {
    "x": 1.3,
    "y": 0.9,
    "yaw": 1.57,
    "frame": "map"
  },
  "paused": false,
  "initial_pose_received": true,
  "initial_pose_confirmed": true,
  "initial_pose_source": "api",
  "pose_available": true,
  "coverage_path_available": true,
  "path_available": true,
  "coverage_map_available": true,
  "coverage_validated": true,
  "ready_to_validate": true,
  "ready_to_start_motion": false,
  "task_finished": false,
  "task_result": null,
  "last_error": null,
  "next_steps": [
    "Poll GET /api/cleaning/status until task_finished is true."
  ],
  "nav": {
    "execution_status": "RUNNING"
  },
  "coverage": {
    "covered_area_m2": 3.5,
    "total_area_m2": 8.2
  }
}
```

Recommended `state` values:

| State       | Meaning                  |
| ----------- | ------------------------ |
| `idle`      | No active cleaning task  |
| `cleaning`  | Robot is cleaning        |
| `paused`    | Cleaning is paused       |
| `completed` | Cleaning completed       |
| `stopped`   | Cleaning stopped by user |
| `error`     | Cleaning failed          |

---

### 8.6 Pause Cleaning

```http
POST /api/cleaning/pause
```

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Cleaning paused.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "paused",
  "task_id": "cleaning_20260624_001"
}
```

---

### 8.7 Resume Cleaning

```http
POST /api/cleaning/resume
```

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Cleaning resumed.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "cleaning",
  "task_id": "cleaning_20260624_001"
}
```

---

### 8.8 Stop Cleaning

```http
POST /api/cleaning/stop
```

Stops the current cleaning task.

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Cleaning stopped.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "stopped",
  "task_id": "cleaning_20260624_001"
}
```

---

### 8.9 Reset Cleaning

```http
POST /api/cleaning/reset
```

Clears the current cleaning task state.

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Cleaning state reset.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "idle",
  "task_id": null
}
```

---

### 8.10 Return Home

```http
POST /api/cleaning/return-home
```

Commands the robot to return home.

#### Response

```json
{
  "success": true,
  "accepted": true,
  "message": "Robot is returning home.",
  "error": null,
  "timestamp": "2026-06-24T12:00:00Z",
  "state": "returning_home"
}
```

---

## 9. Validation Rules

### 9.1 Exploration Start Validation

For:

```http
POST /api/exploration/start
```

Rules:

| Rule                                  | Error              |
| ------------------------------------- | ------------------ |
| `map_name` is missing or empty        | `VALIDATION_ERROR` |
| `mode` is not `automatic` or `manual` | `VALIDATION_ERROR` |
| Robot is already cleaning             | `ROBOT_BUSY`       |
| Robot is already exploring            | `ROBOT_BUSY`       |

---

### 9.2 Manual Drive Validation

For:

```http
POST /api/exploration/manual-drive
```

Rules:

| Rule                             | Error              |
| -------------------------------- | ------------------ |
| Exploration is not active        | `INVALID_STATE`    |
| Exploration mode is not `manual` | `INVALID_STATE`    |
| `command` is invalid             | `VALIDATION_ERROR` |

---

### 9.3 Exploration Switch Validation

For:

```http
POST /api/exploration/switch
```

Rules:

| Rule                                      | Error              |
| ----------------------------------------- | ------------------ |
| Exploration is not active                 | `INVALID_STATE`    |
| `new_mode` is not `automatic` or `manual` | `VALIDATION_ERROR` |

---

### 9.4 Cleaning Start Validation

For:

```http
POST /api/cleaning/start
```

Rules:

| Rule                                                  | Error              |
| ----------------------------------------------------- | ------------------ |
| `map_id` is missing or empty                          | `VALIDATION_ERROR` |
| `cleaning_mode` is missing                            | `VALIDATION_ERROR` |
| `cleaning_mode` is not `full-map` or `sections`       | `VALIDATION_ERROR` |
| `initial_pose` is included in `cleaning/start`        | `VALIDATION_ERROR` |
| `cleaning_mode` is `sections` and `sections` is empty | `VALIDATION_ERROR` |
| Robot is already cleaning                             | `ROBOT_BUSY`       |
| Robot is already exploring                            | `ROBOT_BUSY`       |
| Map does not exist                                    | `MAP_NOT_FOUND`    |

---

## 10. Error Codes

| Code               | Meaning                                          |
| ------------------ | ------------------------------------------------ |
| `VALIDATION_ERROR` | Request body is invalid                          |
| `MAP_NOT_FOUND`    | Requested map does not exist                     |
| `ROBOT_BUSY`       | Robot is already running another task            |
| `INVALID_STATE`    | Action cannot be done in current robot state     |
| `ROS_UNAVAILABLE`  | Required ROS service/topic/action is unavailable |
| `TASK_FAILED`      | Robot task failed                                |
| `INTERNAL_ERROR`   | Unexpected server error                          |

---

## 11. Implementation Notes

### 11.1 Mobile App

The Flutter app should use the endpoints in this document only.

The app should continue to expect these important top-level fields:

* `items` from `GET /api/maps`
* `map_id`
* `map_name`
* `sections`
* `task_id`
* `state`
* `cleaning_mode`
* `progress_percent`
* `pose`

The app should also read:

* `success`
* `message`
* `error`

---

### 11.2 Mock Server

The mock server must implement the same API as this document.

It should not create app-only endpoint shapes that are different from the robot API bridge.

The mock server should be useful for app development, but the request and response bodies must match the real robot bridge.

---

### 11.3 Robot API Bridge

The robot API bridge must implement this same API.

For cleaning:

1. Receive `POST /api/cleaning/start`.
2. Validate `map_id`, `cleaning_mode`, and `sections`.
3. Launch coverage but do not start robot motion.
4. If `cleaning_mode` is `full-map`, clean the full map.
5. If `cleaning_mode` is `sections`, clean only the selected section rectangles.
6. If `processed_map` is provided, use it as the selected-section bounded map.
7. Wait for initial pose from `POST /api/localization/initial-pose` or RViz.
8. Validate the path with `POST /api/cleaning/validate`.
9. Start robot motion with `POST /api/cleaning/start-motion`.
10. Continuously update `/api/cleaning/status`.

For exploration:

1. Receive `POST /api/exploration/start`.
2. Use `map_name` as the final saved map name.
3. Start in `automatic` or `manual` mode.
4. Use `/api/exploration/switch` to change between `automatic` and `manual` during exploration.
5. Use `/api/exploration/manual-drive` for app manual movement.
6. Stop and save through `/api/exploration/stop`.

---

## 12. Required Endpoint Summary

| Method | Endpoint                        | Required |
| ------ | ------------------------------- | -------: |
| `GET`  | `/api/system/health`            |      yes |
| `GET`  | `/api/robot/status`             |      yes |
| `GET`  | `/api/maps`                     |      yes |
| `GET`  | `/api/maps/{map_id}`            |      yes |
| `GET`  | `/api/maps/{map_id}/metadata`   |      yes |
| `PUT`  | `/api/maps/{map_id}/metadata`   |      yes |
| `POST` | `/api/exploration/start`        |      yes |
| `GET`  | `/api/exploration/status`       |      yes |
| `POST` | `/api/exploration/switch`       |      yes |
| `POST` | `/api/exploration/manual-drive` |      yes |
| `POST` | `/api/exploration/stop`         |      yes |
| `POST` | `/api/localization/initial-pose`|      yes |
| `POST` | `/api/cleaning/start`           |      yes |
| `GET`  | `/api/cleaning/status`          |      yes |
| `POST` | `/api/cleaning/validate`        |      yes |
| `POST` | `/api/cleaning/start-motion`    |      yes |
| `POST` | `/api/cleaning/pause`           |      yes |
| `POST` | `/api/cleaning/resume`          |      yes |
| `POST` | `/api/cleaning/stop`            |      yes |
| `POST` | `/api/cleaning/reset`           |      yes |
| `POST` | `/api/cleaning/return-home`     |      yes |
