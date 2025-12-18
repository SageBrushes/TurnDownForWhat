"""
Main FastAPI application with lifespan events.

Initializes the FastAPI app with:
- Lifespan events for startup/shutdown
- API routers (speakers, tts, websocket)
- Static file serving for audio files
- CORS middleware for browser access
- Background tasks for speaker discovery and audio cleanup
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api import speakers, tts, websocket
from app.services import cleanup_service, sonos_service
from app.config import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Audio directory path
AUDIO_DIR = Path(__file__).parent.parent / "static" / "audio"

# Templates directory
templates = Jinja2Templates(directory="templates")


# Background task functions
async def speaker_discovery_task():
    """
    Background task for periodic speaker discovery.

    Runs every SPEAKER_DISCOVERY_INTERVAL_MINUTES to refresh the speaker cache.
    This ensures the speaker list stays up-to-date without requiring manual refresh.
    """
    interval_seconds = settings.SPEAKER_DISCOVERY_INTERVAL_MINUTES * 60
    logger.info(
        f"Speaker discovery task started "
        f"(interval: {settings.SPEAKER_DISCOVERY_INTERVAL_MINUTES} minutes)"
    )

    while True:
        try:
            # Discover speakers with force refresh
            speakers = await sonos_service.discover_speakers(force_refresh=True)
            logger.info(f"Speaker discovery: found {len(speakers)} speaker(s)")
        except Exception as e:
            logger.error(f"Error in speaker discovery task: {e}", exc_info=True)

        # Wait for next interval
        await asyncio.sleep(interval_seconds)


async def audio_cleanup_task():
    """
    Background task for periodic audio file cleanup.

    Runs every hour to delete audio files older than AUDIO_CLEANUP_MAX_AGE_MINUTES.
    This prevents the audio directory from growing indefinitely.
    """
    # Run hourly (3600 seconds)
    interval_seconds = 3600
    logger.info(
        f"Audio cleanup task started "
        f"(interval: 60 minutes, max age: {settings.AUDIO_CLEANUP_MAX_AGE_MINUTES} minutes)"
    )

    while True:
        try:
            # Clean up old files
            stats = await cleanup_service.cleanup_old_audio_files(
                max_age_minutes=settings.AUDIO_CLEANUP_MAX_AGE_MINUTES
            )
            logger.info(
                f"Audio cleanup completed: {stats.deleted_count} deleted, "
                f"{stats.kept_count} kept, {stats.error_count} errors"
            )
        except Exception as e:
            logger.error(f"Error in audio cleanup task: {e}", exc_info=True)

        # Wait for next interval
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan context manager for startup and shutdown events.

    Startup:
    - Ensures static/audio directory exists
    - Starts speaker discovery background task
    - Starts audio cleanup background task

    Shutdown:
    - Cancels background tasks
    - Cleans up resources

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # ========== STARTUP ==========
    logger.info("Application startup initiated")

    # 1. Ensure audio directory exists
    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Audio directory ready: {AUDIO_DIR}")
    except Exception as e:
        logger.error(f"Failed to create audio directory: {e}", exc_info=True)
        # Continue anyway - we'll handle this at runtime if needed

    # 2. Initial speaker discovery to populate cache
    try:
        speakers = await sonos_service.discover_speakers()
        logger.info(f"Initial speaker discovery: found {len(speakers)} speaker(s)")
    except Exception as e:
        logger.warning(f"Initial speaker discovery failed (will retry in background): {e}")

    # 3. Start background tasks
    discovery_task = None
    cleanup_task = None

    try:
        # Start speaker discovery task
        discovery_task = asyncio.create_task(
            speaker_discovery_task(),
            name="speaker_discovery"
        )
        logger.info("Speaker discovery task started")

        # Start audio cleanup task
        cleanup_task = asyncio.create_task(
            audio_cleanup_task(),
            name="audio_cleanup"
        )
        logger.info("Audio cleanup task started")

    except Exception as e:
        logger.error(f"Failed to start background tasks: {e}", exc_info=True)

    logger.info("Application startup complete")

    # ========== RUNTIME ==========
    yield

    # ========== SHUTDOWN ==========
    logger.info("Application shutdown initiated")

    # Cancel background tasks
    tasks_to_cancel = []
    if discovery_task:
        tasks_to_cancel.append(discovery_task)
    if cleanup_task:
        tasks_to_cancel.append(cleanup_task)

    for task in tasks_to_cancel:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Task {task.get_name()} cancelled")
        except Exception as e:
            logger.error(f"Error cancelling task {task.get_name()}: {e}")

    logger.info("Application shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Sonos TTS Web Service",
    description="Text-to-Speech service for Sonos speakers using ElevenLabs",
    version="1.0.0",
    lifespan=lifespan
)


# Configure CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(speakers.router)
app.include_router(tts.router)
app.include_router(websocket.router)

logger.info("API routers included")


# Mount static files for audio serving
# This must be done after including routers to avoid path conflicts
app.mount("/static", StaticFiles(directory="static"), name="static")
logger.info("Static files mounted at /static")


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "sonos-tts-web-service",
        "version": "1.0.0"
    }


# Root endpoint - Serve the HTML dashboard
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Serve the main Sonos control dashboard.

    Returns:
        HTML: The main dashboard interface
    """
    return templates.TemplateResponse("index.html", {"request": request})


# API info endpoint
@app.get("/api")
async def api_info():
    """
    API information endpoint.

    Returns:
        dict: Service and endpoint information
    """
    return {
        "service": "Sonos TTS Web Service",
        "version": "1.0.0",
        "description": "Text-to-Speech service for Sonos speakers using ElevenLabs",
        "endpoints": {
            "api_docs": "/docs",
            "health": "/health",
            "speakers": "/api/speakers",
            "tts": "/api/tts",
            "websocket": "/ws"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )
