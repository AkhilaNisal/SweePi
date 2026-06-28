# Command Lifecycle Fields

Command endpoints under `/api` separate transport acceptance from command-step
completion. Endpoint-specific response fields stay at the top level; responses
are not wrapped in a `data` object.

Every robot command response should include:

| Field | Meaning |
| --- | --- |
| `success` | From the app point of view, the next expected step may proceed. |
| `accepted` | The API bridge accepted the request and attempted the ROS/mock action. |
| `completed` | This endpoint's immediate command step reached its confirmation condition. |
| `task_finished` | The whole long-running task is finished. Start commands normally return `false`. |
| `task_result` | Final task result such as `completed`, `stopped`, `reset`, `failed`, or `map_saved`. |
| `state` | Current robot/task state or the next state the app should display. |
| `command` | Stable command name for client logic, such as `set_initial_pose`. |
| `next_steps` | Optional ordered hints for the next API calls. |
| `error` | `null` on success, otherwise `{ "code": "...", "details": { ... } }`. |

`accepted=true` does not mean the robot task succeeded. For example, initial
pose may be published but fail localization confirmation, returning
`accepted=true`, `completed=false`, and `success=false`.

The mobile app must advance to the next cleaning step only when the previous
command response has both `success=true` and `completed=true`. Long-running
cleaning, exploration, and return-home commands require polling status endpoints
until `task_finished=true`.

## Cleaning Sequence

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

`POST /api/localization/initial-pose` validates the pose against the active
cleaning coverage map when one is available, publishes `/initialpose`, then
waits for `map -> base_link` pose confirmation within tolerant distance/yaw
limits. A publish alone does not set `completed=true`.

`POST /api/cleaning/start-motion` does not auto-validate. It returns
`VALIDATION_REQUIRED` unless `POST /api/cleaning/validate` completed
successfully for the current coverage path.
