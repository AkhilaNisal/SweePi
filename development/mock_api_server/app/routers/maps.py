from fastapi import APIRouter, HTTPException

from app.core.state import (
    list_map_metadata,
    read_map_data,
    read_map_metadata,
    update_map_metadata as store_update_map_metadata,
)
from app.models.maps import MapMetadataUpdateRequest


router = APIRouter(prefix="/api/maps", tags=["Maps"])


@router.get("")
def list_maps():
    """
    Return metadata for all maps currently stored by the mock robot.
    The actual occupancy map is fetched separately using GET /api/maps/{map_id}.
    """
    return {"items": list_map_metadata()}


@router.get("/{map_id}")
def get_map(map_id: str):
    """
    Return the actual map data for the given map_id.
    """
    try:
        return read_map_data(map_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Map not found")


@router.get("/{map_id}/metadata")
def get_map_metadata(map_id: str):
    """
    Return only the metadata for the given map_id.
    """
    try:
        return read_map_metadata(map_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Map not found")


@router.put("/{map_id}/metadata")
def update_map_metadata(map_id: str, req: MapMetadataUpdateRequest):
    """
    Update map metadata after the mobile app divides the map into sections.
    The robot remains the source of truth, so this mock stores the updated
    section metadata under the robot's map storage.
    """
    try:
        return store_update_map_metadata(map_id, req.name, req.sections)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Map not found")
