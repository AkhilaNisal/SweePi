from typing import Any, Dict, List
from pydantic import BaseModel, Field


class CleaningStartRequest(BaseModel):
    map_id: str = Field(..., examples=["map_001"])
    sections: List[Dict[str, Any]] = Field(default_factory=list)
