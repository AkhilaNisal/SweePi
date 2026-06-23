from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import robot, exploration, maps, cleaning


app = FastAPI(
    title="SweePi Mock API",
    description="Hardcoded mock API server for SweePi mobile app integration",
    version="0.1.0",
)

# Allows Flutter Web, Android emulator, real phone on Wi-Fi, browser, and Postman
# to access the local mock API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(robot.router)
app.include_router(exploration.router)
app.include_router(maps.router)
app.include_router(cleaning.router)


@app.get("/")
def root():
    return {
        "name": "SweePi Mock API",
        "status": "running",
        "docs": "/docs",
        "robot_status": "/api/robot/status",
    }
