from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CleaningStartRequest(BaseModel):
    map_id: str = Field(..., examples=["map_001"])
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    processed_map: Optional[Dict[str, Any]] = None
    initial_pose: Optional[Dict[str, Any]] = None
