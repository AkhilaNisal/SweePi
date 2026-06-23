from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
import uuid

app = FastAPI(title="SweePi Mock API")

robot_state = {
    "robot_id": "sweepi-mock-001",
    "state": "idle",
    "mode": "automatic",
    "battery": {
        "percent": 87,
        "charging": False
    },
    "pose": {
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
        "frame": "map"
    },
    "map": {
        "map_id": None
    },
    "cleaning": {
        "task_id": None,
        "map_id": None,
        "sections": [],
        "progress_percent": 0.0
    },
    "nav": {
        "execution_status": "IDLE"
    },
    "errors": [],
    "warnings": []
}

maps: Dict[str, Dict[str, Any]] = {
    "map_001": {
        "metadata": {
            "map_id": "map_001",
            "name": "living_room",
            "created_at": "2026-06-23T00:00:00+05:30",
            "width": 100,
            "height": 100,
            "resolution": 0.05,
            "sections": [
                {
                    "section_id": "sec_001",
                    "name": "Left side",
                    "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]
                }
            ]
        },
        "map": {
            "map_id": "map_001",
            "name": "living_room",
            "resolution": 0.05,
            "origin": {
                "x": -2.5,
                "y": -2.5
            },
            "width": 100,
            "height": 100,
            "occupancy": [0] * 10000
        }
    }
}


class ExplorationStartRequest(BaseModel):
    map_name: str
    mode: Literal["manual", "automatic"]


class ManualDriveRequest(BaseModel):
    command: Literal["forward", "backward", "rotate_left", "rotate_right", "stop"]
    speed: Optional[float] = 0.2


class CleaningStartRequest(BaseModel):
    map_id: str
    sections: List[Dict[str, Any]] = []


@app.get("/api/robot/status")
def get_robot_status():
    return robot_state


@app.post("/api/exploration/start")
def start_exploration(req: ExplorationStartRequest):
    robot_state["state"] = "exploring"
    robot_state["mode"] = req.mode
    robot_state["map"]["map_id"] = None

    return {
        "accepted": True,
        "state": "exploring",
        "mode": req.mode,
        "map_name": req.map_name,
        "message": "Exploration started"
    }


@app.get("/api/exploration/status")
def exploration_status():
    return {
        "state": robot_state["state"],
        "mode": robot_state["mode"],
        "map_available": robot_state["state"] in ["exploring", "idle"],
        "message": "Mock exploration running"
    }


@app.post("/api/exploration/stop")
def stop_exploration():
    map_id = f"map_{uuid.uuid4().hex[:6]}"

    maps[map_id] = {
        "metadata": {
            "map_id": map_id,
            "name": "new_mock_map",
            "created_at": datetime.now().isoformat(),
            "width": 100,
            "height": 100,
            "resolution": 0.05,
            "sections": []
        },
        "map": {
            "map_id": map_id,
            "name": "new_mock_map",
            "resolution": 0.05,
            "origin": {
                "x": -2.5,
                "y": -2.5
            },
            "width": 100,
            "height": 100,
            "occupancy": [0] * 10000
        }
    }

    robot_state["state"] = "idle"
    robot_state["map"]["map_id"] = map_id

    return {
        "accepted": True,
        "state": "idle",
        "map_saved": True,
        "map_id": map_id,
        "message": "Exploration stopped and mock map saved"
    }


@app.post("/api/exploration/manual-drive")
def manual_drive(req: ManualDriveRequest):
    if robot_state["state"] != "exploring" or robot_state["mode"] != "manual":
        return {
            "accepted": False,
            "message": "Manual drive is allowed only during manual exploration"
        }

    return {
        "accepted": True,
        "command": req.command,
        "speed": req.speed,
        "message": f"Mock robot command: {req.command}"
    }


@app.get("/api/maps")
def list_maps():
    return {
        "items": [m["metadata"] for m in maps.values()]
    }


@app.get("/api/maps/{map_id}")
def get_map(map_id: str):
    if map_id not in maps:
        raise HTTPException(status_code=404, detail="Map not found")

    return maps[map_id]["map"]


@app.get("/api/maps/{map_id}/metadata")
def get_map_metadata(map_id: str):
    if map_id not in maps:
        raise HTTPException(status_code=404, detail="Map not found")

    return maps[map_id]["metadata"]


@app.post("/api/cleaning/start")
def start_cleaning(req: CleaningStartRequest):
    if req.map_id not in maps:
        return {
            "accepted": False,
            "message": "Map not found"
        }

    robot_state["state"] = "cleaning"
    robot_state["cleaning"]["task_id"] = f"task_{uuid.uuid4().hex[:6]}"
    robot_state["cleaning"]["map_id"] = req.map_id
    robot_state["cleaning"]["sections"] = req.sections
    robot_state["cleaning"]["progress_percent"] = 0.0
    robot_state["nav"]["execution_status"] = "CLEANING"

    return {
        "accepted": True,
        "task_id": robot_state["cleaning"]["task_id"],
        "state": "cleaning",
        "map_id": req.map_id,
        "sections": req.sections,
        "message": "Mock cleaning started"
    }


@app.post("/api/cleaning/pause")
def pause_cleaning():
    if robot_state["state"] != "cleaning":
        return {
            "accepted": False,
            "message": "Robot is not cleaning"
        }

    robot_state["state"] = "paused"
    robot_state["nav"]["execution_status"] = "PAUSED"

    return {
        "accepted": True,
        "state": "paused"
    }


@app.post("/api/cleaning/resume")
def resume_cleaning():
    if robot_state["state"] != "paused":
        return {
            "accepted": False,
            "message": "Robot is not paused"
        }

    robot_state["state"] = "cleaning"
    robot_state["nav"]["execution_status"] = "CLEANING"

    return {
        "accepted": True,
        "state": "cleaning"
    }


@app.post("/api/cleaning/stop")
def stop_cleaning():
    robot_state["state"] = "idle"
    robot_state["cleaning"]["progress_percent"] = 0.0
    robot_state["nav"]["execution_status"] = "IDLE"

    return {
        "accepted": True,
        "state": "idle",
        "message": "Mock cleaning stopped"
    }