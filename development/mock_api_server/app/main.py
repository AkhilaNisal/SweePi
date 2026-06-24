from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import robot, exploration, maps, cleaning
from app.core.responses import error_body, ok


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


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(str(exc.detail), "INTERNAL_ERROR"),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    first_error = exc.errors()[0] if exc.errors() else {}
    loc = first_error.get("loc", [])
    field = loc[-1] if loc else None
    return JSONResponse(
        status_code=422,
        content=error_body(
            "Request body is invalid.",
            "VALIDATION_ERROR",
            {"field": field, "errors": exc.errors()},
            accepted=False,
        ),
    )


@app.get("/api/system/health")
def health():
    return ok(
        "API server is healthy.",
        status="ok",
        robot_connected=True,
        server="sweepi_mock_api",
    )


@app.get("/")
def root():
    return {
        "name": "SweePi Mock API",
        "status": "running",
        "docs": "/docs",
        "robot_status": "/api/robot/status",
    }
