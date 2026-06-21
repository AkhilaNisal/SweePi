# SweePi API Bridge Guide

The API bridge exposes the SweePi simulation and robot stack to HTTP clients
such as `curl`, Postman, and the Flutter app.

Default simulation URLs:

```text
HTTP:      http://localhost:8080
WebSocket: ws://localhost:8765
```

The implementation lives in:

```text
src/raspberry_pi/src/sweepi_api_bridge/sweepi_api_bridge/api_bridge_node.py
```

## Run The Simulation

From the ROS 2 workspace:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select sweepi_bringup sweepi_coverage sweepi_api_bridge sweepi_slam sweepi_exploration
source install/setup.bash
ros2 launch sweepi_bringup sweepi_sim_full.launch.py
```

`sweepi_sim_full.launch.py` starts Gazebo, Nav2, SLAM Toolbox, the idle
wavefront explorer, coverage nodes, coverage manager, and `api_bridge_node`.
Exploration does not move the robot until the API calls
`POST /api/v1/exploration/start`.

Check that the bridge is listening:

```bash
ss -ltnp | grep -E "8080|8765"
curl http://localhost:8080/api/v1/robot/status
```

## Operation Sequence

1. Launch simulation:

   ```bash
   ros2 launch sweepi_bringup sweepi_sim_full.launch.py
   ```

2. Check bridge and robot status:

   ```bash
   curl http://localhost:8080/api/v1/robot/status
   ```

3. Start exploration and name the map that will be saved later:

   ```bash
   curl -X POST http://localhost:8080/api/v1/exploration/start \
     -H "Content-Type: application/json" \
     -d '{"area_name":"first_floor"}'
   ```

4. Check exploration status:

   ```bash
   curl http://localhost:8080/api/v1/exploration/status
   ```

5. Wait until a map is available:

   ```bash
   curl http://localhost:8080/api/v1/maps/current
   ```

   The response should include `"available": true`. If cleaning starts before
   `/map` is available, the bridge can respond with `"accepted": false`.

6. Stop exploration and save the current live `/map` using `area_name`:

   ```bash
   curl -X POST http://localhost:8080/api/v1/exploration/stop
   ```

7. Start full-map cleaning:

   ```bash
   curl -X POST http://localhost:8080/api/v1/cleaning/start
   ```

8. Query progress:

   ```bash
   curl http://localhost:8080/api/v1/robot/status
   curl http://localhost:8080/api/v1/maps/current
   ```

9. Pause, resume, or stop when supported by the current robot state:

   ```bash
   curl -X POST http://localhost:8080/api/v1/cleaning/pause
   curl -X POST http://localhost:8080/api/v1/cleaning/resume
   curl -X POST http://localhost:8080/api/v1/cleaning/stop
   ```

The active state is reported through `GET /api/v1/robot/status` as `state` and
`nav.execution_status`. The API bridge does not currently expose the manager's
`allowed_commands` list, but the underlying coverage manager allows:

```text
idle     -> start_cleaning
cleaning -> pause_cleaning, stop_cleaning
paused   -> resume_cleaning, stop_cleaning
error    -> stop_cleaning
```

## Exploration / Mapping API

These endpoints control the `wavefront_explorer` node through ROS services.
The API bridge stores the `area_name` from the start request and uses it when
saving the live `/map` during stop.

### POST /api/v1/exploration/start

Purpose: Start autonomous mapping/exploration and set the map name that will be
used when the map is saved.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"first_floor"}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/exploration/start
Body:   raw JSON
```

```json
{
  "area_name": "first_floor"
}
```

Expected response:

```json
{
  "accepted": true,
  "state": "exploring",
  "area_name": "first_floor",
  "message": "Exploration started"
}
```

If the explorer is not running, the response is:

```json
{
  "accepted": false,
  "state": "idle",
  "area_name": "first_floor",
  "message": "/exploration/start is unavailable"
}
```

### GET /api/v1/exploration/status

Purpose: Return the latest exploration status cached by the API bridge.

Curl:

```bash
curl http://localhost:8080/api/v1/exploration/status
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/exploration/status
Body:   none
```

Expected response:

```json
{
  "state": "exploring",
  "area_name": "first_floor",
  "map_available": true,
  "frontiers_remaining": 10,
  "last_goal": {
    "x": 1.2,
    "y": 0.5
  },
  "message": "Navigating to frontier (1.20, 0.50)"
}
```

Reliable fields are `state`, `area_name`, `map_available`,
`frontiers_remaining`, `last_goal`, and `message`. `frontiers_remaining` is the
latest detected frontier count from the explorer loop. `last_goal` is `null`
until the explorer sends its first Nav2 goal. Detailed completion reason,
coverage quality, and per-frontier history are not exposed yet.

### POST /api/v1/exploration/stop

Purpose: Stop autonomous exploration and save the current live `/map` using the
`area_name` supplied to `POST /api/v1/exploration/start`.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/exploration/stop
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/exploration/stop
Body:   none
```

Expected response when a live `/map` is available:

```json
{
  "accepted": true,
  "state": "idle",
  "area_name": "first_floor",
  "map_saved": true,
  "map_id": "first_floor",
  "message": "Exploration stopped and map saved"
}
```

Expected response when no live `/map` is available:

```json
{
  "accepted": true,
  "state": "idle",
  "area_name": "first_floor",
  "map_saved": false,
  "message": "Exploration stopped, but no live /map was available to save"
}
```

## Postman Basics

For HTTP requests:

1. Create a new HTTP request.
2. Set the method and URL from the endpoint reference below.
3. For endpoints with a JSON body, choose `Body` -> `raw` -> `JSON`.
4. Add header `Content-Type: application/json` when sending a JSON body.
5. Click `Send`.

For WebSocket:

1. Create a new WebSocket request.
2. Connect to `ws://localhost:8765`.
3. Watch incoming messages. The bridge does not require client messages.

## HTTP Endpoint Reference

All endpoints return JSON. Failed commands generally still return HTTP `200`
with `"accepted": false` when the bridge reached the ROS service but the command
was rejected. Malformed JSON or invalid request data returns HTTP `400`.
Unknown paths return HTTP `404`.

### GET /api/v1/robot/status

Purpose: Get the robot, cleaning, map, navigation, warning, and error state.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/robot/status
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/robot/status
Body:   none
```

Expected response:

```json
{
  "robot_id": "sweepi-sim-001",
  "state": "idle",
  "mode": "auto",
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
  "cleaning": {
    "task_id": null,
    "type": null,
    "progress_percent": 0.0,
    "selection": {
      "selection_id": null,
      "room_ids": [],
      "zones": [],
      "no_go_zones": [],
      "map_id": null,
      "map_revision": null
    }
  },
  "map": {
    "map_id": null,
    "revision": 0
  },
  "nav": {
    "execution_status": "WAITING_FOR_PATH",
    "coverage_stats": ""
  },
  "errors": [],
  "warnings": []
}
```

`pose` is `null` until the bridge can look up the `map -> base_link` transform.

### GET /api/v1/maps/current

Purpose: Get the live occupancy map, coverage map, current selection, metadata,
and robot pose.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/maps/current
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/maps/current
Body:   none
```

Expected response before `/map` is available:

```json
{
  "map_id": null,
  "revision": 0,
  "available": false,
  "selection": {
    "selection_id": null,
    "room_ids": [],
    "zones": [],
    "no_go_zones": [],
    "map_id": null,
    "map_revision": null
  }
}
```

Expected response after `/map` is available:

```json
{
  "map_id": "live_map",
  "revision": 123456,
  "available": true,
  "resolution": 0.05,
  "origin": {
    "x": -10.0,
    "y": -10.0
  },
  "width": 400,
  "height": 400,
  "occupancy": [0, 0, 100],
  "coverage": [0, 0, 100],
  "selection": {},
  "metadata": {
    "map_id": "live_map",
    "name": "live_map",
    "rooms": [],
    "no_go_zones": [],
    "labels": []
  },
  "robot_pose": {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "frame": "map"
  }
}
```

The `occupancy` and `coverage` arrays are full occupancy-grid arrays, so this
response can be large.

### GET /api/v1/maps

Purpose: List maps saved by the bridge under `runtime/raspberry_pi/maps`.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/maps
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/maps
Body:   none
```

Expected response:

```json
{
  "items": [
    {
      "map_id": "test_map",
      "yaml_path": "/home/akhila-wedamestrige/SweePi/runtime/raspberry_pi/maps/test_map.yaml",
      "pgm_path": "/home/akhila-wedamestrige/SweePi/runtime/raspberry_pi/maps/test_map.pgm",
      "metadata": {
        "map_id": "test_map",
        "name": "test_map",
        "rooms": [],
        "no_go_zones": [],
        "labels": []
      }
    }
  ]
}
```

### POST /api/v1/maps/save

Purpose: Save the current live `/map` as PGM, YAML, and metadata files.

Required body:

```json
{
  "name": "test_map"
}
```

`name` is optional. If omitted, the bridge uses `map_<unix_timestamp>`.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/maps/save \
  -H "Content-Type: application/json" \
  -d '{"name":"test_map"}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/maps/save
Body:   raw JSON
```

```json
{
  "name": "test_map"
}
```

Expected response:

```json
{
  "accepted": true,
  "map_id": "test_map",
  "pgm_path": "/home/akhila-wedamestrige/SweePi/runtime/raspberry_pi/maps/test_map.pgm",
  "yaml_path": "/home/akhila-wedamestrige/SweePi/runtime/raspberry_pi/maps/test_map.yaml",
  "metadata_path": "/home/akhila-wedamestrige/SweePi/runtime/raspberry_pi/maps/test_map.meta.json"
}
```

If no live map is available, the response is HTTP `400`:

```json
{
  "error": "No live /map is available to save"
}
```

### POST /api/v1/maps/load

Purpose: Mark a saved map as active in the bridge.

Required body:

```json
{
  "map_id": "test_map"
}
```

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/maps/load \
  -H "Content-Type: application/json" \
  -d '{"map_id":"test_map"}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/maps/load
Body:   raw JSON
```

```json
{
  "map_id": "test_map"
}
```

Expected response:

```json
{
  "accepted": true,
  "active_map_id": "test_map",
  "robot_apply_supported": false,
  "note": "Saved map selection is tracked by the bridge, but applying it to the localization stack is still a planned simulation-first step."
}
```

Important: this endpoint does not currently apply the saved map to Nav2 or the
localization stack.

### GET /api/v1/maps/{map_id}/metadata

Purpose: Get editable map metadata such as rooms, no-go zones, and labels.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/maps/test_map/metadata
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/maps/test_map/metadata
Body:   none
```

Expected response:

```json
{
  "map_id": "test_map",
  "name": "test_map",
  "rooms": [],
  "no_go_zones": [],
  "labels": []
}
```

If metadata has not been saved yet, the bridge returns default empty metadata.

### PUT /api/v1/maps/{map_id}/metadata

Purpose: Replace map metadata.

Required body:

```json
{
  "name": "Apartment",
  "rooms": [
    {
      "id": "living_room",
      "name": "Living Room",
      "polygon": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0]]
    }
  ],
  "no_go_zones": [],
  "labels": []
}
```

Curl:

```bash
curl -X PUT http://localhost:8080/api/v1/maps/test_map/metadata \
  -H "Content-Type: application/json" \
  -d '{"name":"Apartment","rooms":[],"no_go_zones":[],"labels":[]}'
```

Postman:

```text
Method: PUT
URL:    http://localhost:8080/api/v1/maps/test_map/metadata
Body:   raw JSON
```

Expected response:

```json
{
  "map_id": "test_map",
  "name": "Apartment",
  "rooms": [],
  "no_go_zones": [],
  "labels": []
}
```

### PUT /api/v1/cleaning/selection

Purpose: Set the selected rooms, selected zones, and no-go zones for selected
cleaning. The bridge publishes the selection to `/coverage_selection`.

Required body:

```json
{
  "selection_id": "sel_demo",
  "map_id": "live_map",
  "map_revision": 123456,
  "room_ids": [],
  "zones": [
    {
      "id": "zone_1",
      "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
    }
  ],
  "no_go_zones": []
}
```

`selection_id`, `map_id`, and `map_revision` are optional. Each zone or no-go
polygon must contain at least three `[x, y]` points. `room_ids` are resolved
from saved map metadata when possible.

Curl:

```bash
curl -X PUT http://localhost:8080/api/v1/cleaning/selection \
  -H "Content-Type: application/json" \
  -d '{"map_id":"live_map","room_ids":[],"zones":[{"id":"zone_1","polygon":[[0,0],[1,0],[1,1]]}],"no_go_zones":[]}'
```

Postman:

```text
Method: PUT
URL:    http://localhost:8080/api/v1/cleaning/selection
Body:   raw JSON
```

Expected response:

```json
{
  "accepted": true,
  "selection": {
    "selection_id": "sel_demo",
    "map_id": "live_map",
    "map_revision": 123456,
    "room_ids": [],
    "rooms": [],
    "zones": [
      {
        "id": "zone_1",
        "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
      }
    ],
    "no_go_zones": [],
    "updated_at": "2026-06-21T00:00:00+00:00"
  }
}
```

### POST /api/v1/cleaning/start

Purpose: Start full-map cleaning through `/manager/start_cleaning`.

Optional body:

```json
{
  "task_id": "task_demo",
  "command_id": "cmd_001",
  "schedule_id": "sch_001"
}
```

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/start
```

With a task id:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/start \
  -H "Content-Type: application/json" \
  -d '{"task_id":"task_demo","command_id":"cmd_001"}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/cleaning/start
Body:   none, or raw JSON with task_id/command_id/schedule_id
```

Expected accepted response:

```json
{
  "accepted": true,
  "task_id": "task_demo",
  "state": "cleaning"
}
```

Expected rejected response:

```json
{
  "accepted": false,
  "message": "Cannot start cleaning before /map is available"
}
```

### POST /api/v1/cleaning/start-selected

Purpose: Start selected cleaning using the current selection.

Required precondition: first call `PUT /api/v1/cleaning/selection` with at
least one `zone` or `room_id`.

Optional body:

```json
{
  "task_id": "task_selected_demo",
  "command_id": "cmd_002"
}
```

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/start-selected \
  -H "Content-Type: application/json" \
  -d '{"task_id":"task_selected_demo"}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/cleaning/start-selected
Body:   none, or raw JSON with task_id/command_id/schedule_id
```

Expected accepted response:

```json
{
  "accepted": true,
  "task_id": "task_selected_demo",
  "state": "cleaning"
}
```

Expected response when no selection has been set:

```json
{
  "error": "Selected cleaning requires at least one zone or room"
}
```

### POST /api/v1/cleaning/stop

Purpose: Stop or cancel the current cleaning task through
`/manager/stop_cleaning`.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/stop
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/cleaning/stop
Body:   none
```

Expected response:

```json
{
  "accepted": true,
  "message": "..."
}
```

If the robot is idle:

```json
{
  "accepted": false,
  "message": "Cannot stop cleaning while state=idle"
}
```

### POST /api/v1/cleaning/pause

Purpose: Pause cleaning by canceling the active coverage execution while keeping
paused context in the manager.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/pause
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/cleaning/pause
Body:   none
```

Expected response:

```json
{
  "accepted": true,
  "message": "..."
}
```

If not currently cleaning:

```json
{
  "accepted": false,
  "message": "Cannot pause cleaning while state=idle"
}
```

### POST /api/v1/cleaning/resume

Purpose: Resume cleaning from paused state.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/cleaning/resume
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/cleaning/resume
Body:   none
```

Expected response:

```json
{
  "accepted": true,
  "message": "..."
}
```

If not paused:

```json
{
  "accepted": false,
  "message": "Cannot resume cleaning while state=idle"
}
```

### POST /api/v1/robot/return-to-dock

Purpose: Request return-to-dock through `/manager/return_to_dock`.

Required body: none.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/robot/return-to-dock
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/robot/return-to-dock
Body:   none
```

Current expected response:

```json
{
  "accepted": false,
  "message": "Return to dock is still a planned simulation-first feature and is not automated in the current stack."
}
```

### GET /api/v1/history

Purpose: List cleaning history recorded by the bridge.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/history
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/history
Body:   none
```

Expected response:

```json
{
  "items": [
    {
      "task_id": "task_demo",
      "task_type": "full",
      "map_id": "live_map",
      "selection": {},
      "started_at": "2026-06-21T00:00:00+00:00",
      "ended_at": null,
      "result": null,
      "coverage_percent": null,
      "notes": {
        "command_id": "cmd_001"
      }
    }
  ]
}
```

When the manager reports a terminal status, `ended_at`, `result`, and
`coverage_percent` are updated.

### GET /api/v1/schedules

Purpose: List saved cleaning schedules.

Required body: none.

Curl:

```bash
curl http://localhost:8080/api/v1/schedules
```

Postman:

```text
Method: GET
URL:    http://localhost:8080/api/v1/schedules
Body:   none
```

Expected response:

```json
{
  "items": [
    {
      "id": "sch_weekday",
      "enabled": true,
      "timezone": "Asia/Colombo",
      "days": ["MON", "TUE"],
      "time_local": "09:30",
      "map_id": "live_map",
      "selection": {},
      "created_at": "2026-06-21T00:00:00+00:00",
      "updated_at": "2026-06-21T00:00:00+00:00",
      "last_run_at": null,
      "next_run_at": null
    }
  ]
}
```

### POST /api/v1/schedules

Purpose: Create or replace a schedule.

Required body:

```json
{
  "id": "sch_weekday",
  "enabled": true,
  "timezone": "Asia/Colombo",
  "days": ["MON", "TUE", "WED", "THU", "FRI"],
  "time_local": "09:30",
  "map_id": "live_map",
  "selection": {
    "room_ids": [],
    "zones": [],
    "no_go_zones": []
  }
}
```

Only `time_local` is required by the bridge. `id` is optional; if omitted, the
bridge creates one.

Curl:

```bash
curl -X POST http://localhost:8080/api/v1/schedules \
  -H "Content-Type: application/json" \
  -d '{"id":"sch_weekday","enabled":true,"timezone":"Asia/Colombo","days":["MON","TUE","WED","THU","FRI"],"time_local":"09:30","map_id":"live_map","selection":{}}'
```

Postman:

```text
Method: POST
URL:    http://localhost:8080/api/v1/schedules
Body:   raw JSON
```

Expected response:

```json
{
  "id": "sch_weekday",
  "enabled": true,
  "timezone": "Asia/Colombo",
  "days": ["MON", "TUE", "WED", "THU", "FRI"],
  "time_local": "09:30",
  "map_id": "live_map",
  "selection": {},
  "created_at": "2026-06-21T00:00:00+00:00",
  "updated_at": "2026-06-21T00:00:00+00:00",
  "last_run_at": null,
  "next_run_at": null
}
```

### PUT /api/v1/schedules/{schedule_id}

Purpose: Replace an existing schedule or create it with the path id.

Required body: same as `POST /api/v1/schedules`, except the path controls the
schedule id.

Curl:

```bash
curl -X PUT http://localhost:8080/api/v1/schedules/sch_weekday \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"timezone":"Asia/Colombo","days":["MON"],"time_local":"09:30","map_id":"live_map","selection":{}}'
```

Postman:

```text
Method: PUT
URL:    http://localhost:8080/api/v1/schedules/sch_weekday
Body:   raw JSON
```

Expected response: same shape as `POST /api/v1/schedules`.

### DELETE /api/v1/schedules/{schedule_id}

Purpose: Delete a schedule.

Required body: none.

Curl:

```bash
curl -X DELETE http://localhost:8080/api/v1/schedules/sch_weekday
```

Postman:

```text
Method: DELETE
URL:    http://localhost:8080/api/v1/schedules/sch_weekday
Body:   none
```

Expected response:

```json
{
  "deleted": true
}
```

If the id did not exist:

```json
{
  "deleted": false
}
```

## WebSocket Behavior

Connect to:

```text
ws://localhost:8765
```

The bridge sends JSON text messages. It does not currently require or process
application-level client messages. It only responds to WebSocket ping frames
with pong frames.

On connect, the bridge sends:

```json
{
  "type": "status.snapshot",
  "payload": {
    "robot_id": "sweepi-sim-001",
    "state": "idle",
    "mode": "auto"
  }
}
```

During runtime, it broadcasts:

```json
{
  "type": "status.update",
  "payload": {}
}
```

`status.update` is sent when coverage percentage, coverage stats, manager
status, selection, or task context changes. The payload has the same shape as
`GET /api/v1/robot/status`.

```json
{
  "type": "map.updated",
  "payload": {
    "map_revision": 123456
  }
}
```

`map.updated` is sent when the live occupancy map or coverage map updates.
Clients should then call `GET /api/v1/maps/current` if they need fresh map
arrays.

```json
{
  "type": "task.completed",
  "payload": {
    "task_id": "task_demo",
    "result": "SUCCEEDED",
    "coverage_percent": 98.5
  }
}
```

`task.completed` is sent when the manager reports one of these terminal
execution statuses:

```text
SUCCEEDED
COMPLETED_WITH_SKIPS
FAILED
BLOCKED_DYNAMIC_OBJECT
CANCELED
```

Flutter app usage:

1. Open one WebSocket connection to `ws://<robot-ip>:8765`.
2. Use `status.snapshot` to initialize UI state.
3. Use `status.update` to refresh robot state, cleaning state, progress, errors,
   and warnings.
4. Use `map.updated` as an invalidation event, then fetch
   `GET /api/v1/maps/current` only when the map view is visible or stale.
5. Use `task.completed` to close active-task UI and refresh history with
   `GET /api/v1/history`.

Manual testing options:

```bash
websocat ws://localhost:8765
```

or:

```bash
wscat -c ws://localhost:8765
```

Postman can also test the WebSocket directly with a WebSocket request to
`ws://localhost:8765`.

Normal `curl` is not a WebSocket client, so use it only for the HTTP endpoints.

## Currently Missing Or Partial Operations

Already supported:

```text
start full cleaning  -> POST /api/v1/cleaning/start
start selected       -> POST /api/v1/cleaning/start-selected
pause cleaning       -> POST /api/v1/cleaning/pause
resume cleaning      -> POST /api/v1/cleaning/resume
stop/cancel cleaning -> POST /api/v1/cleaning/stop
robot status         -> GET  /api/v1/robot/status
coverage percentage  -> included at cleaning.progress_percent
cleaning state       -> included at state and nav.execution_status
current map          -> GET  /api/v1/maps/current
history              -> GET  /api/v1/history
schedules            -> /api/v1/schedules
```

Partial:

```text
return to dock -> endpoint exists, but currently returns accepted=false
map load       -> bridge tracks active saved map, but does not apply it to Nav2/localization
battery        -> fields exist, but values are null
```

Suggested clean endpoint names for future work:

```text
POST /api/v1/robot/emergency-stop
POST /api/v1/robot/clear-emergency-stop
POST /api/v1/navigation/goal
POST /api/v1/navigation/cancel
GET  /api/v1/navigation/status
GET  /api/v1/cleaning/state
GET  /api/v1/coverage/status
GET  /api/v1/maps/current/summary
GET  /api/v1/maps/current/image?layer=occupancy
GET  /api/v1/maps/current/image?layer=coverage
POST /api/v1/maps/load-and-apply
GET  /api/v1/robot/battery
```

The current API already exposes enough to launch simulation, start cleaning,
pause/resume/stop, query progress, inspect the live map, and drive a Flutter UI
with WebSocket status updates.
