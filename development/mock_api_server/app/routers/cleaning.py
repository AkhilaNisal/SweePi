import uuid

from fastapi import APIRouter

from app.core.responses import fail, ok
from app.core.state import robot_state, exploration_state, map_exists, reset_cleaning_state
from app.models.cleaning import CleaningStartRequest


router = APIRouter(prefix="/api/cleaning", tags=["Cleaning"])


@router.post("/start")
def start_cleaning(req: CleaningStartRequest):
    map_id = (req.map_id or "").strip()
    if not map_id:
        fail(
            400,
            "map_id is required.",
            "VALIDATION_ERROR",
            {"field": "map_id"},
            accepted=False,
        )
    if req.cleaning_mode is None:
        fail(
            400,
            "cleaning_mode is required.",
            "VALIDATION_ERROR",
            {"field": "cleaning_mode"},
            accepted=False,
        )
    if req.cleaning_mode not in {"full-map", "sections"}:
        fail(
            400,
            "Invalid cleaning_mode. Allowed values are full-map and sections.",
            "VALIDATION_ERROR",
            {
                "field": "cleaning_mode",
                "allowed_values": ["full-map", "sections"],
            },
            accepted=False,
        )
    if req.initial_pose is not None:
        fail(
            400,
            "initial_pose must be sent separately after cleaning/start.",
            "VALIDATION_ERROR",
            {
                "field": "initial_pose",
                "use_endpoint": "/api/localization/initial-pose",
            },
            accepted=False,
        )
    if req.cleaning_mode == "sections" and not req.sections:
        fail(
            400,
            "sections must contain at least one section when cleaning_mode is sections.",
            "VALIDATION_ERROR",
            {"field": "sections", "cleaning_mode": "sections"},
            accepted=False,
        )
    if robot_state["cleaning"]["active"]:
        fail(409, "Robot is already cleaning.", "ROBOT_BUSY", accepted=False)
    if exploration_state["active"]:
        fail(409, "Robot is already exploring.", "ROBOT_BUSY", accepted=False)
    if not map_exists(map_id):
        fail(404, "Map not found.", "MAP_NOT_FOUND", {"map_id": map_id}, accepted=False)
    if req.processed_map is not None:
        expected_cells = req.processed_map.width * req.processed_map.height
        if len(req.processed_map.occupancy) != expected_cells:
            fail(
                400,
                "processed_map.occupancy length must match width * height.",
                "VALIDATION_ERROR",
                {"field": "processed_map.occupancy"},
                accepted=False,
            )

    sections = [_model_to_dict(section) for section in req.sections]
    task_id = f"cleaning_{uuid.uuid4().hex[:8]}"

    robot_state["state"] = "waiting_for_initial_pose"
    robot_state["cleaning"]["active"] = True
    robot_state["cleaning"]["task_id"] = task_id
    robot_state["cleaning"]["map_id"] = map_id
    robot_state["cleaning"]["cleaning_mode"] = req.cleaning_mode
    robot_state["cleaning"]["sections"] = sections
    robot_state["cleaning"]["processed_map"] = (
        _model_to_dict(req.processed_map) if req.processed_map is not None else None
    )
    robot_state["cleaning"]["initial_pose"] = None
    robot_state["cleaning"]["validated"] = False
    robot_state["cleaning"]["progress_percent"] = 0.0
    robot_state["nav"]["execution_status"] = "WAITING_FOR_INITIAL_POSE"

    return ok(
        "Coverage prepared. Waiting for initial pose from mobile app or RViz.",
        accepted=True,
        task_id=task_id,
        state="waiting_for_initial_pose",
        map_id=map_id,
        cleaning_mode=req.cleaning_mode,
        sections=sections,
        initial_pose=None,
        initial_pose_required=True,
        progress_percent=0.0,
    )


@router.post("/validate")
def validate_cleaning():
    cleaning = robot_state["cleaning"]
    if not cleaning["active"]:
        fail(409, "No cleaning task is prepared.", "INVALID_STATE", accepted=False)
    if cleaning["initial_pose"] is None:
        fail(
            409,
            "Initial pose is required before validation.",
            "INVALID_STATE",
            {"required_endpoint": "/api/localization/initial-pose"},
            accepted=False,
        )

    robot_state["state"] = "validated"
    robot_state["cleaning"]["validated"] = True
    robot_state["nav"]["execution_status"] = "VALIDATED"

    return ok(
        "Cleaning path validated.",
        accepted=True,
        state="validated",
        task_id=cleaning["task_id"],
    )


@router.post("/start-motion")
def start_cleaning_motion():
    cleaning = robot_state["cleaning"]
    if not cleaning["active"]:
        fail(409, "No cleaning task is prepared.", "INVALID_STATE", accepted=False)
    if cleaning["initial_pose"] is None:
        fail(
            409,
            "Initial pose is required before starting motion.",
            "INVALID_STATE",
            {"required_endpoint": "/api/localization/initial-pose"},
            accepted=False,
        )
    if not cleaning["validated"]:
        fail(
            409,
            "Cleaning path must be validated before starting motion.",
            "INVALID_STATE",
            {"required_endpoint": "/api/cleaning/validate"},
            accepted=False,
        )

    robot_state["state"] = "cleaning"
    robot_state["nav"]["execution_status"] = "RUNNING"

    return ok(
        "Cleaning motion started.",
        accepted=True,
        state="cleaning",
        task_id=cleaning["task_id"],
    )


@router.get("/status")
def cleaning_status():
    cleaning = robot_state["cleaning"]
    return ok(
        "Cleaning status fetched.",
        active=cleaning["active"],
        state=robot_state["state"] if cleaning["active"] else "idle",
        task_id=cleaning["task_id"],
        map_id=cleaning["map_id"],
        cleaning_mode=cleaning["cleaning_mode"],
        sections=[
            {"section_id": section["section_id"], "name": section.get("name")}
            for section in cleaning["sections"]
        ],
        progress_percent=cleaning["progress_percent"],
        pose=robot_state["pose"],
        nav=robot_state["nav"],
        coverage={"covered_area_m2": 0.0, "total_area_m2": 0.0},
    )


@router.post("/pause")
def pause_cleaning():
    if robot_state["state"] != "cleaning":
        fail(409, "Robot is not cleaning.", "INVALID_STATE", accepted=False)

    robot_state["state"] = "paused"
    robot_state["nav"]["execution_status"] = "PAUSED"

    return ok(
        "Cleaning paused.",
        accepted=True,
        state="paused",
        task_id=robot_state["cleaning"]["task_id"],
    )


@router.post("/resume")
def resume_cleaning():
    if robot_state["state"] != "paused":
        fail(409, "Robot is not paused.", "INVALID_STATE", accepted=False)

    robot_state["state"] = "cleaning"
    robot_state["nav"]["execution_status"] = "RUNNING"

    return ok(
        "Cleaning resumed.",
        accepted=True,
        state="cleaning",
        task_id=robot_state["cleaning"]["task_id"],
    )


@router.post("/stop")
def stop_cleaning():
    task_id = robot_state["cleaning"]["task_id"]
    robot_state["state"] = "stopped"
    robot_state["cleaning"]["active"] = False
    robot_state["nav"]["execution_status"] = "IDLE"

    return ok("Cleaning stopped.", accepted=True, state="stopped", task_id=task_id)


@router.post("/reset")
def reset_cleaning():
    robot_state["state"] = "idle"
    robot_state["nav"]["execution_status"] = "IDLE"
    reset_cleaning_state()

    return ok("Cleaning state reset.", accepted=True, state="idle", task_id=None)


@router.post("/return-home")
def return_home():
    robot_state["state"] = "returning_home"
    robot_state["nav"]["execution_status"] = "RETURNING_HOME"

    return ok("Robot is returning home.", accepted=True, state="returning_home")


def _model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
