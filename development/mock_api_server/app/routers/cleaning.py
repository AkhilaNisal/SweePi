import uuid

from fastapi import APIRouter

from app.core.state import robot_state, map_exists, reset_cleaning_state
from app.models.cleaning import CleaningStartRequest


router = APIRouter(prefix="/api/cleaning", tags=["Cleaning"])


@router.post("/start")
def start_cleaning(req: CleaningStartRequest):
    """
    Start cleaning using a selected map and optional selected sections.
    If sections is empty, the mock treats it as full-map cleaning.
    """
    if not map_exists(req.map_id):
        return {
            "accepted": False,
            "message": "Map not found",
        }

    processed_map_error = _validate_processed_map(req.processed_map)
    if processed_map_error is not None:
        return {
            "accepted": False,
            "message": processed_map_error,
        }

    initial_pose, initial_pose_error = _normalize_initial_pose(req.initial_pose)
    if initial_pose_error is not None:
        return {
            "accepted": False,
            "message": initial_pose_error,
        }

    task_id = f"task_{uuid.uuid4().hex[:6]}"

    robot_state["state"] = "cleaning"
    robot_state["cleaning"]["task_id"] = task_id
    robot_state["cleaning"]["map_id"] = req.map_id
    robot_state["cleaning"]["sections"] = req.sections
    robot_state["cleaning"]["processed_map"] = req.processed_map
    robot_state["cleaning"]["initial_pose"] = initial_pose
    robot_state["cleaning"]["progress_percent"] = 0.0
    robot_state["nav"]["execution_status"] = "CLEANING"

    return {
        "accepted": True,
        "task_id": task_id,
        "state": "cleaning",
        "map_id": req.map_id,
        "sections": req.sections,
        "message": "Mock cleaning started",
    }


def _validate_processed_map(processed_map):
    if processed_map is None:
        return None
    if not isinstance(processed_map, dict):
        return "processed_map must be an object"

    width = processed_map.get("width")
    height = processed_map.get("height")
    resolution = processed_map.get("resolution")
    origin = processed_map.get("origin")
    occupancy = processed_map.get("occupancy")

    if not isinstance(width, int) or width <= 0:
        return "processed_map.width must be a positive integer"
    if not isinstance(height, int) or height <= 0:
        return "processed_map.height must be a positive integer"
    if not isinstance(resolution, (int, float)) or resolution <= 0:
        return "processed_map.resolution must be positive"
    if not isinstance(origin, dict):
        return "processed_map.origin must be an object"
    if not isinstance(origin.get("x"), (int, float)):
        return "processed_map.origin.x must be numeric"
    if not isinstance(origin.get("y"), (int, float)):
        return "processed_map.origin.y must be numeric"
    if "yaw" in origin and not isinstance(origin.get("yaw"), (int, float)):
        return "processed_map.origin.yaw must be numeric"
    if not isinstance(occupancy, list):
        return "processed_map.occupancy must be a list"
    if len(occupancy) != width * height:
        return "processed_map.occupancy length must match width * height"
    if not all(isinstance(value, int) for value in occupancy):
        return "processed_map.occupancy values must be integers"
    return None


def _normalize_initial_pose(initial_pose):
    if initial_pose is None:
        return None, None
    if not isinstance(initial_pose, dict):
        return None, "initial_pose must be an object"

    x = initial_pose.get("x")
    y = initial_pose.get("y")
    yaw = initial_pose.get("yaw")
    frame = initial_pose.get("frame", "map")

    if not isinstance(x, (int, float)):
        return None, "initial_pose.x must be numeric"
    if not isinstance(y, (int, float)):
        return None, "initial_pose.y must be numeric"
    if not isinstance(yaw, (int, float)):
        return None, "initial_pose.yaw must be numeric"
    if not isinstance(frame, str) or not frame:
        return None, "initial_pose.frame must be a non-empty string"

    return {
        "x": float(x),
        "y": float(y),
        "yaw": float(yaw),
        "frame": frame,
    }, None


@router.post("/pause")
def pause_cleaning():
    if robot_state["state"] != "cleaning":
        return {
            "accepted": False,
            "message": "Robot is not cleaning",
        }

    robot_state["state"] = "paused"
    robot_state["nav"]["execution_status"] = "PAUSED"

    return {
        "accepted": True,
        "state": "paused",
    }


@router.post("/resume")
def resume_cleaning():
    if robot_state["state"] != "paused":
        return {
            "accepted": False,
            "message": "Robot is not paused",
        }

    robot_state["state"] = "cleaning"
    robot_state["nav"]["execution_status"] = "CLEANING"

    return {
        "accepted": True,
        "state": "cleaning",
    }


@router.post("/stop")
def stop_cleaning():
    robot_state["state"] = "idle"
    robot_state["nav"]["execution_status"] = "IDLE"
    reset_cleaning_state()

    return {
        "accepted": True,
        "state": "idle",
        "message": "Mock cleaning stopped",
    }
