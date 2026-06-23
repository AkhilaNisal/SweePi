from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MapMetadataUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, examples=["Living Room"])
    sections: List[Dict[str, Any]] = Field(default_factory=list)
