from datetime import datetime
from typing import Any, Dict
import uuid


robot_state: Dict[str, Any] = {
    "robot_id": "sweepi-mock-001",
    "state": "idle",
    "mode": "automatic",
    "battery": {
        "percent": 87,
        "charging": False,
    },
    "pose": {
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
        "frame": "map",
    },
    "map": {
        "map_id": None,
    },
    "cleaning": {
        "task_id": None,
        "map_id": None,
        "sections": [],
        "progress_percent": 0.0,
    },
    "nav": {
        "execution_status": "IDLE",
    },
    "errors": [],
    "warnings": [],
}


exploration_state: Dict[str, Any] = {
    "active": False,
    "map_name": None,
    "mode": "automatic",
}


maps: Dict[str, Dict[str, Any]] = {
    "map_001": {
        "metadata": {
            "map_id": "map_001",
            "name": "living_room",
            "created_at": "2026-06-23T00:00:00+05:30",
            "updated_at": "2026-06-23T00:00:00+05:30",
            "width": 100,
            "height": 100,
            "resolution": 0.05,
            "sections": [
                {
                    "section_id": "sec_001",
                    "name": "Left side",
                    "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]],
                }
            ],
        },
        "map": {
            "map_id": "map_001",
            "name": "living_room",
            "resolution": 0.05,
            "origin": {
                "x": -2.5,
                "y": -2.5,
            },
            "width": 100,
            "height": 100,
            "occupancy": [0] * 10000,
        },
    }
}


def create_mock_map(map_name: str) -> str:
    """
    Create a fake saved map and return its generated map_id.
    This simulates the robot saving a map after exploration stops.
    """
    map_id = f"map_{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()

    maps[map_id] = {
        "metadata": {
            "map_id": map_id,
            "name": map_name,
            "created_at": now,
            "updated_at": now,
            "width": 100,
            "height": 100,
            "resolution": 0.05,
            "sections": [],
        },
        "map": {
            "map_id": map_id,
            "name": map_name,
            "resolution": 0.05,
            "origin": {
                "x": -2.5,
                "y": -2.5,
            },
            "width": 100,
            "height": 100,
            "occupancy": [0] * 10000,
        },
    }

    return map_id


def reset_cleaning_state() -> None:
    robot_state["cleaning"]["task_id"] = None
    robot_state["cleaning"]["map_id"] = None
    robot_state["cleaning"]["sections"] = []
    robot_state["cleaning"]["progress_percent"] = 0.0
