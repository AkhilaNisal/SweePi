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

    task_id = f"task_{uuid.uuid4().hex[:6]}"

    robot_state["state"] = "cleaning"
    robot_state["cleaning"]["task_id"] = task_id
    robot_state["cleaning"]["map_id"] = req.map_id
    robot_state["cleaning"]["sections"] = req.sections
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
