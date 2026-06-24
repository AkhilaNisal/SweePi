from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid


MAPS_DIR = Path(__file__).resolve().parents[2] / "maps"
MAPS_DIR.mkdir(exist_ok=True)


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
        "map_id": "my_room_map",
        "name": "My Room",
    },
    "cleaning": {
        "active": False,
        "task_id": None,
        "map_id": None,
        "cleaning_mode": None,
        "sections": [],
        "processed_map": None,
        "initial_pose": None,
        "progress_percent": 0.0,
    },
    "exploration": {
        "active": False,
        "map_name": None,
        "mode": None,
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
    "mode": None,
}


def list_map_metadata() -> List[Dict[str, Any]]:
    return [read_map_metadata(path.stem.replace(".meta", "")) for path in sorted(MAPS_DIR.glob("*.meta.json"))]


def map_exists(map_id: str) -> bool:
    return _metadata_path(map_id).exists()


def read_map_metadata(map_id: str) -> Dict[str, Any]:
    path = _metadata_path(map_id)
    if not path.exists():
        raise FileNotFoundError(map_id)

    with path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    yaml_data = _read_yaml(map_id)
    width, height = _read_pgm_size(map_id)
    metadata["origin"] = _origin_from_yaml(yaml_data)
    if metadata.get("width") is None:
        metadata["width"] = width
    if metadata.get("height") is None:
        metadata["height"] = height
    if metadata.get("resolution") is None:
        metadata["resolution"] = yaml_data.get("resolution", 0.05)
    return metadata


def update_map_metadata(
    map_id: str,
    name: Optional[str],
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    metadata = read_map_metadata(map_id)
    if name is not None:
        metadata["name"] = name
    metadata["sections"] = sections
    metadata["updated_at"] = now_iso()

    with _metadata_path(map_id).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)
        file.write("\n")

    return metadata


def read_map_data(map_id: str) -> Dict[str, Any]:
    metadata = read_map_metadata(map_id)
    yaml_data = _read_yaml(map_id)
    width, height, pixels = _read_pgm(map_id)
    metadata_sections = metadata.get("sections", [])
    return {
        "map_id": map_id,
        "name": metadata.get("name", map_id),
        "resolution": float(yaml_data.get("resolution", metadata.get("resolution", 0.05))),
        "origin": _origin_from_yaml(yaml_data),
        "width": width,
        "height": height,
        "occupancy": [_pixel_to_occupancy(pixel) for pixel in pixels],
        "sections": metadata_sections,
    }


def create_mock_map(map_name: str) -> str:
    """
    Create a fake saved map and return its generated map_id.
    This simulates the robot saving a map after exploration stops.
    """
    map_id = _safe_map_id(map_name)
    if map_exists(map_id):
        map_id = f"{map_id}_{uuid.uuid4().hex[:6]}"
    now = now_iso()
    _write_free_pgm(map_id, width=100, height=100)
    _write_yaml(map_id, resolution=0.05, origin=[-2.5, -2.5, 0.0])

    metadata = {
        "map_id": map_id,
        "name": map_name,
        "created_at": now,
        "updated_at": now,
        "width": 100,
        "height": 100,
        "resolution": 0.05,
        "origin": {"x": -2.5, "y": -2.5, "yaw": 0.0},
        "sections": [],
    }
    with _metadata_path(map_id).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)
        file.write("\n")

    return map_id


def reset_cleaning_state() -> None:
    robot_state["cleaning"]["active"] = False
    robot_state["cleaning"]["task_id"] = None
    robot_state["cleaning"]["map_id"] = None
    robot_state["cleaning"]["cleaning_mode"] = None
    robot_state["cleaning"]["sections"] = []
    robot_state["cleaning"]["processed_map"] = None
    robot_state["cleaning"]["initial_pose"] = None
    robot_state["cleaning"]["progress_percent"] = 0.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_map_id(map_name: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in map_name.strip())
    return safe or f"map_{uuid.uuid4().hex[:6]}"


def _origin_from_yaml(yaml_data: Dict[str, Any]) -> Dict[str, float]:
    origin = yaml_data.get("origin", [0.0, 0.0, 0.0])
    return {
        "x": float(origin[0]) if len(origin) > 0 else 0.0,
        "y": float(origin[1]) if len(origin) > 1 else 0.0,
        "yaw": float(origin[2]) if len(origin) > 2 else 0.0,
    }


def _metadata_path(map_id: str) -> Path:
    return MAPS_DIR / f"{map_id}.meta.json"


def _yaml_path(map_id: str) -> Path:
    return MAPS_DIR / f"{map_id}.yaml"


def _pgm_path(map_id: str) -> Path:
    return MAPS_DIR / f"{map_id}.pgm"


def _read_yaml(map_id: str) -> Dict[str, Any]:
    path = _yaml_path(map_id)
    if not path.exists():
        return {"resolution": 0.05, "origin": [0.0, 0.0, 0.0], "image": f"{map_id}.pgm"}

    data: Dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            data[key.strip()] = [
                float(item.strip()) for item in value[1:-1].split(",") if item.strip()
            ]
        else:
            try:
                data[key.strip()] = float(value)
            except ValueError:
                data[key.strip()] = value
    return data


def _write_yaml(map_id: str, resolution: float, origin: List[float]) -> None:
    _yaml_path(map_id).write_text(
        "\n".join(
            [
                f"image: {map_id}.pgm",
                f"resolution: {resolution}",
                f"origin: [{origin[0]}, {origin[1]}, {origin[2]}]",
                "negate: 0",
                "occupied_thresh: 0.65",
                "free_thresh: 0.25",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _read_pgm_size(map_id: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        width, height, _ = _read_pgm(map_id, pixels=False)
        return width, height
    except FileNotFoundError:
        return None, None


def _read_pgm(map_id: str, pixels: bool = True) -> Tuple[int, int, List[int]]:
    path = _pgm_path(map_id)
    data = path.read_bytes()
    index = 0

    def next_token() -> str:
        nonlocal index
        while index < len(data) and chr(data[index]).isspace():
            index += 1
        if index < len(data) and data[index] == ord("#"):
            while index < len(data) and data[index] not in (10, 13):
                index += 1
            return next_token()
        start = index
        while index < len(data) and not chr(data[index]).isspace():
            index += 1
        return data[start:index].decode("ascii")

    magic = next_token()
    if magic not in {"P2", "P5"}:
        raise ValueError(f"Unsupported PGM format: {magic}")
    width = int(next_token())
    height = int(next_token())
    max_value = int(next_token())

    if not pixels:
        return width, height, []

    if magic == "P2":
        values = [int(next_token()) for _ in range(width * height)]
    else:
        while index < len(data) and chr(data[index]).isspace():
            index += 1
        raw_pixels = data[index : index + width * height]
        values = list(raw_pixels)

    if max_value <= 0:
        return width, height, values
    if max_value != 255:
        values = [round(value * 255 / max_value) for value in values]
    return width, height, values


def _write_free_pgm(map_id: str, width: int, height: int) -> None:
    header = f"P5\n{width} {height}\n255\n".encode("ascii")
    pixels = bytes([255]) * width * height
    _pgm_path(map_id).write_bytes(header + pixels)


def _pixel_to_occupancy(pixel: int) -> int:
    if pixel >= 250:
        return 0
    if pixel <= 10:
        return 100
    return -1
