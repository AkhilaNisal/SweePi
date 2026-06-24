from fastapi import APIRouter

from app.core.responses import fail, ok
from app.core.state import robot_state, exploration_state, create_mock_map
from app.models.exploration import (
    ExplorationStartRequest,
    ExplorationSwitchRequest,
    ManualDriveRequest,
)


router = APIRouter(prefix="/api/exploration", tags=["Exploration"])


@router.post("/start")
def start_exploration(req: ExplorationStartRequest):
    map_name = req.map_name.strip()
    if not map_name:
        fail(
            400,
            "map_name is required.",
            "VALIDATION_ERROR",
            {"field": "map_name"},
            accepted=False,
        )
    if robot_state["cleaning"]["active"]:
        fail(409, "Robot is already cleaning.", "ROBOT_BUSY", accepted=False)
    if exploration_state["active"]:
        fail(409, "Robot is already exploring.", "ROBOT_BUSY", accepted=False)

    exploration_state["active"] = True
    exploration_state["map_name"] = map_name
    exploration_state["mode"] = req.mode

    robot_state["state"] = "exploring"
    robot_state["mode"] = req.mode
    robot_state["map"]["map_id"] = None
    robot_state["map"]["name"] = None
    robot_state["exploration"] = {
        "active": True,
        "map_name": map_name,
        "mode": req.mode,
    }
    robot_state["nav"]["execution_status"] = "EXPLORING"

    return ok(
        "Exploration started.",
        accepted=True,
        state="exploring",
        mode=req.mode,
        map_name=map_name,
    )


@router.get("/status")
def exploration_status():
    return ok(
        "Exploration status fetched.",
        active=exploration_state["active"],
        state="exploring" if exploration_state["active"] else "idle",
        mode=exploration_state["mode"],
        map_name=exploration_state["map_name"],
        progress_percent=None,
        pose=robot_state["pose"],
        map_available=robot_state["map"]["map_id"] is not None,
    )


@router.post("/switch")
def switch_exploration(req: ExplorationSwitchRequest):
    if not exploration_state["active"]:
        fail(
            409,
            "Exploration is not active.",
            "INVALID_STATE",
            {"field": "new_mode"},
            accepted=False,
        )

    exploration_state["mode"] = req.new_mode
    robot_state["mode"] = req.new_mode
    robot_state["exploration"]["mode"] = req.new_mode

    return ok(
        "Exploration mode switched.",
        accepted=True,
        state="exploring",
        mode=req.new_mode,
    )


@router.post("/manual-drive")
def manual_drive(req: ManualDriveRequest):
    if not exploration_state["active"]:
        fail(
            409,
            "Exploration is not active.",
            "INVALID_STATE",
            {"state": robot_state["state"]},
            accepted=False,
        )
    if exploration_state["mode"] != "manual":
        fail(
            409,
            "Manual drive is allowed only during manual exploration.",
            "INVALID_STATE",
            {"mode": exploration_state["mode"]},
            accepted=False,
        )

    return ok(
        "Manual drive command accepted.",
        accepted=True,
        command=req.command,
        speed=req.speed,
        state="exploring",
    )


@router.post("/stop")
def stop_exploration():
    map_name = exploration_state["map_name"] or "new_mock_map"
    map_id = create_mock_map(map_name)

    exploration_state["active"] = False
    exploration_state["map_name"] = None
    exploration_state["mode"] = None

    robot_state["state"] = "idle"
    robot_state["mode"] = "automatic"
    robot_state["map"]["map_id"] = map_id
    robot_state["map"]["name"] = map_name
    robot_state["exploration"] = {
        "active": False,
        "map_name": None,
        "mode": None,
    }
    robot_state["nav"]["execution_status"] = "IDLE"

    return ok(
        "Exploration stopped and map saved.",
        accepted=True,
        state="idle",
        map_saved=True,
        map_id=map_id,
        map_name=map_name,
    )
