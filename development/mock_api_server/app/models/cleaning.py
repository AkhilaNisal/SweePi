from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.maps import MapSection


class Pose(BaseModel):
    x: float
    y: float
    yaw: float
    frame: str = "map"


class MapOrigin(BaseModel):
    x: float
    y: float
    yaw: float = 0.0


class ProcessedMap(BaseModel):
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    resolution: float = Field(..., gt=0)
    origin: MapOrigin
    occupancy: List[int]


class CleaningStartRequest(BaseModel):
    map_id: Optional[str] = Field(default=None, examples=["map_001"])
    cleaning_mode: Optional[str] = None
    sections: List[MapSection] = Field(default_factory=list)
    processed_map: Optional[ProcessedMap] = None
    initial_pose: Optional[Pose] = None
