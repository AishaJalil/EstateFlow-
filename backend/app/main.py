import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.predictive_maintenance import run_predictive_maintenance_batch
from app.api.routes import (
    health,
    inspections,
    maintenance,
    messaging,
    notifications,
    predictive,
    profile,
    properties,
    vendors,
    calendar,
)
from app.services.vendor_outreach import (
    process_outreach_timeouts,
    process_pending_vendor_messages,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

def _cors_origins() -> list[str]:
    return [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]

app = FastAPI(
    title="EstateFlow API",
    description="Multi-agent property management platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(properties.router, prefix="/api")
app.include_router(vendors.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(inspections.router, prefix="/api")
app.include_router(predictive.router, prefix="/api")
app.include_router(messaging.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")


async def _predictive_weekly_loop() -> None:
    """Predictive Maintenance Agent (#12) — runs weekly in the background."""
    interval_sec = 7 * 24 * 3600
    await asyncio.sleep(120)  # let API start before first scheduled run
    while True:
        try:
            stats = await run_predictive_maintenance_batch()
            logger.info("Predictive maintenance batch: %s", stats)
        except Exception:
            logger.exception("Predictive maintenance batch failed")
        await asyncio.sleep(interval_sec)


async def _vendor_outreach_loop() -> None:
    """Poll vendor replies and 24h outreach timeouts."""
    settings = get_settings()
    interval = max(60, settings.vendor_outreach_poll_seconds)
    await asyncio.sleep(30)
    while True:
        try:
            n_msgs = await process_pending_vendor_messages()
            n_time = await process_outreach_timeouts()
            if n_msgs or n_time:
                logger.info("Outreach worker: %s replies, %s timeouts", n_msgs, n_time)
        except Exception:
            logger.exception("Vendor outreach worker failed")
        await asyncio.sleep(interval)


@app.on_event("startup")
async def startup_predictive_scheduler() -> None:
    asyncio.create_task(_predictive_weekly_loop())
    asyncio.create_task(_vendor_outreach_loop())


@app.get("/")
async def root():
    return {"service": "EstateFlow", "docs": "/docs"}
