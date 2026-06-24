from typing import List, Optional
from pydantic import BaseModel, Field


class SectionBounds(BaseModel):
    x: float
    y: float
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)


class MapSection(BaseModel):
    section_id: str = Field(..., min_length=1)
    name: Optional[str] = None
    bounds: SectionBounds


class MapMetadataUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, examples=["Living Room"])
    sections: List[MapSection] = Field(default_factory=list)
