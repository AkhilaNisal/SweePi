from fastapi import APIRouter

from app.core.state import robot_state
from app.core.responses import ok


router = APIRouter(prefix="/api/robot", tags=["Robot"])


@router.get("/status")
def get_robot_status():
    return ok("Robot status fetched.", **robot_state)
