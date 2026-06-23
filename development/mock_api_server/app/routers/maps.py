from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.state import maps
from app.models.maps import MapMetadataUpdateRequest


router = APIRouter(prefix="/api/maps", tags=["Maps"])


@router.get("")
def list_maps():
    """
    Return metadata for all maps currently stored by the mock robot.
    The actual occupancy map is fetched separately using GET /api/maps/{map_id}.
    """
    return {
        "items": [m["metadata"] for m in maps.values()]
    }


@router.get("/{map_id}")
def get_map(map_id: str):
    """
    Return the actual map data for the given map_id.
    """
    if map_id not in maps:
        raise HTTPException(status_code=404, detail="Map not found")

    return maps[map_id]["map"]


@router.get("/{map_id}/metadata")
def get_map_metadata(map_id: str):
    """
    Return only the metadata for the given map_id.
    """
    if map_id not in maps:
        raise HTTPException(status_code=404, detail="Map not found")

    return maps[map_id]["metadata"]


@router.put("/{map_id}/metadata")
def update_map_metadata(map_id: str, req: MapMetadataUpdateRequest):
    """
    Update map metadata after the mobile app divides the map into sections.
    The robot remains the source of truth, so this mock stores the updated
    section metadata under the robot's map storage.
    """
    if map_id not in maps:
        raise HTTPException(status_code=404, detail="Map not found")

    metadata = maps[map_id]["metadata"]

    if req.name is not None:
        metadata["name"] = req.name
        maps[map_id]["map"]["name"] = req.name

    metadata["sections"] = req.sections
    metadata["updated_at"] = datetime.now().isoformat()

    return metadata
