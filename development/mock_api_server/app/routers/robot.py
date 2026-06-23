from fastapi import APIRouter

from app.core.state import robot_state


router = APIRouter(prefix="/api/robot", tags=["Robot"])


@router.get("/status")
def get_robot_status():
    return robot_state
