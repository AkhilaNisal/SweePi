from fastapi import APIRouter

from app.core.state import robot_state, exploration_state, create_mock_map
from app.models.exploration import ExplorationStartRequest, ManualDriveRequest


router = APIRouter(prefix="/api/exploration", tags=["Exploration"])


@router.post("/start")
def start_exploration(req: ExplorationStartRequest):
    exploration_state["active"] = True
    exploration_state["map_name"] = req.map_name
    exploration_state["mode"] = req.mode

    robot_state["state"] = "exploring"
    robot_state["mode"] = req.mode
    robot_state["map"]["map_id"] = None
    robot_state["nav"]["execution_status"] = "EXPLORING"

    return {
        "accepted": True,
        "state": "exploring",
        "mode": req.mode,
        "map_name": req.map_name,
        "message": "Exploration started",
    }


@router.get("/status")
def exploration_status():
    return {
        "state": robot_state["state"],
        "mode": robot_state["mode"],
        "map_name": exploration_state["map_name"],
        "map_available": robot_state["map"]["map_id"] is not None,
        "message": (
            "Mock exploration running"
            if exploration_state["active"]
            else "Exploration is not running"
        ),
    }


@router.post("/stop")
def stop_exploration():
    map_name = exploration_state["map_name"] or "new_mock_map"
    map_id = create_mock_map(map_name)

    exploration_state["active"] = False
    exploration_state["map_name"] = None

    robot_state["state"] = "idle"
    robot_state["map"]["map_id"] = map_id
    robot_state["nav"]["execution_status"] = "IDLE"

    return {
        "accepted": True,
        "state": "idle",
        "map_saved": True,
        "map_id": map_id,
        "message": "Exploration stopped and mock map saved",
    }


@router.post("/manual-drive")
def manual_drive(req: ManualDriveRequest):
    if robot_state["state"] != "exploring" or robot_state["mode"] != "manual":
        return {
            "accepted": False,
            "message": "Manual drive is allowed only during manual exploration",
        }

    return {
        "accepted": True,
        "command": req.command,
        "speed": req.speed,
        "message": f"Mock robot command: {req.command}",
    }
