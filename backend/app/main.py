from app.routers import vehicles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import traffic
from app.routers import events
from app.config import get_settings
from app.routers import simulation
from app.routers import alerts, cameras, city, health, system, transitions

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="City-wide AI engine for multi-camera ANPR trajectory tracking "
                "and urban traffic analytics (SIH26127).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles.router)
app.include_router(health.router)
app.include_router(cameras.router)
app.include_router(city.router)
app.include_router(system.router)
app.include_router(transitions.router)
app.include_router(traffic.router)
app.include_router(events.router)
app.include_router(simulation.router)
app.include_router(alerts.router)


@app.get("/")
async def root():
    return {
        "service": "URBANTRACE API",
        "docs": "/docs",
        "health": "/api/health",
    }