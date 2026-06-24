from typing import Literal, Optional
from pydantic import BaseModel, Field


class ExplorationStartRequest(BaseModel):
    map_name: str = Field(..., min_length=1, examples=["living_room"])
    mode: Literal["manual", "automatic"] = Field(..., examples=["automatic"])


class ExplorationSwitchRequest(BaseModel):
    new_mode: Literal["manual", "automatic"]


class ManualDriveRequest(BaseModel):
    command: Literal[
        "forward",
        "backward",
        "left",
        "right",
        "stop",
    ]
    speed: Optional[float] = Field(default=0.2, ge=0.0, le=1.0)
