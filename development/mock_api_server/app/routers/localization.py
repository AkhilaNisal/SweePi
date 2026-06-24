from fastapi import APIRouter

from app.core.responses import fail, ok
from app.core.state import map_exists, robot_state
from app.models.cleaning import InitialPoseRequest


router = APIRouter(prefix="/api/localization", tags=["Localization"])


@router.post("/initial-pose")
def set_initial_pose(req: InitialPoseRequest):
    map_id = (req.map_id or "").strip()
    if not map_id:
        fail(
            400,
            "map_id is required.",
            "VALIDATION_ERROR",
            {"field": "map_id"},
            accepted=False,
        )
    if not map_exists(map_id):
        fail(404, "Map not found.", "MAP_NOT_FOUND", {"map_id": map_id}, accepted=False)

    cleaning = robot_state["cleaning"]
    if not cleaning["active"]:
        fail(409, "No cleaning task is prepared.", "INVALID_STATE", accepted=False)
    if cleaning["map_id"] != map_id:
        fail(
            409,
            "Initial pose map_id must match the prepared cleaning task.",
            "INVALID_STATE",
            {"field": "map_id", "expected": cleaning["map_id"]},
            accepted=False,
        )

    initial_pose = {
        "x": req.x,
        "y": req.y,
        "yaw": req.yaw,
        "frame": req.frame,
    }
    robot_state["pose"] = initial_pose
    robot_state["state"] = "waiting_for_validation"
    robot_state["cleaning"]["initial_pose"] = initial_pose
    robot_state["cleaning"]["validated"] = False
    robot_state["nav"]["execution_status"] = "INITIAL_POSE_RECEIVED"

    return ok(
        "Initial pose published.",
        accepted=True,
        initial_pose_received=True,
        initial_pose_source="api",
        initial_pose=initial_pose,
    )
