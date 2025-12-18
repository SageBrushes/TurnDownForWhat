"""
Cleanup Service - Audio File Management

Handles automatic cleanup of old TTS audio files.
Includes file locking detection to prevent deleting files being played.
"""

import asyncio
import time
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import logging

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:
    # Allow imports during testing when apscheduler may not be installed
    AsyncIOScheduler = None


# Configuration
AUDIO_DIR = Path(__file__).parent.parent.parent / "static" / "audio"

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None

# Logger
logger = logging.getLogger(__name__)


# Models
class CleanupStats(BaseModel):
    """Statistics from a cleanup operation."""
    deleted_count: int = Field(0, description="Number of files deleted")
    kept_count: int = Field(0, description="Number of files kept")
    error_count: int = Field(0, description="Number of errors encountered")
    duration_seconds: float = Field(0.0, description="Time taken for cleanup")


# Core Functions
async def cleanup_old_audio_files(max_age_minutes: int) -> CleanupStats:
    """
    Delete audio files older than specified age.

    Only processes MP3 files in the root of AUDIO_DIR.
    Skips files that are currently in use (being played).

    Args:
        max_age_minutes: Maximum age of files to keep (in minutes)

    Returns:
        CleanupStats with operation results
    """
    start_time = time.time()
    stats = CleanupStats()

    # Ensure audio directory exists
    if not AUDIO_DIR.exists():
        logger.warning(f"Audio directory does not exist: {AUDIO_DIR}")
        stats.duration_seconds = time.time() - start_time
        return stats

    # Current time for age calculation
    current_time = time.time()
    max_age_seconds = max_age_minutes * 60

    # Process files
    try:
        # Get all MP3 files in root directory only (not subdirectories)
        mp3_files = [f for f in AUDIO_DIR.iterdir() if f.is_file() and f.suffix == ".mp3"]

        for file_path in mp3_files:
            try:
                # Check file age
                file_mtime = file_path.stat().st_mtime
                file_age_seconds = current_time - file_mtime

                if file_age_seconds > max_age_seconds:
                    # File is old enough to delete
                    # Check if file is currently in use
                    if is_file_in_use(file_path):
                        logger.info(f"Skipping in-use file: {file_path.name}")
                        stats.kept_count += 1
                        continue

                    # Delete the file
                    await asyncio.to_thread(os.remove, file_path)
                    logger.info(f"Deleted old audio file: {file_path.name}")
                    stats.deleted_count += 1
                else:
                    # File is still fresh
                    stats.kept_count += 1

            except Exception as e:
                # Log error but continue with other files
                logger.error(f"Error processing file {file_path.name}: {e}")
                stats.error_count += 1

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        stats.error_count += 1

    # Record duration
    stats.duration_seconds = time.time() - start_time

    logger.info(
        f"Cleanup complete: {stats.deleted_count} deleted, "
        f"{stats.kept_count} kept, {stats.error_count} errors "
        f"in {stats.duration_seconds:.2f}s"
    )

    return stats


def is_file_in_use(file_path: Path) -> bool:
    """
    Check if a file is currently in use (being read/written).

    This is platform-specific:
    - Windows: Can detect open files reliably
    - Unix/Mac: Limited detection for read-only opens

    Args:
        file_path: Path to the file to check

    Returns:
        True if file appears to be in use, False otherwise
    """
    # Basic check: does file exist?
    if not file_path.exists():
        return False

    try:
        # Try to open file in exclusive write mode
        # If it's being read by Sonos, this will work on Unix/Mac
        # On Windows, this will fail if file is open in any mode
        with open(file_path, "a"):
            pass

        # If we can open it, it's probably not in use
        # Note: This isn't perfect on Unix/Mac for read-only access
        # but it's the best we can do without platform-specific code
        return False

    except (OSError, IOError):
        # File is locked or inaccessible
        return True


# Scheduler Functions
async def start_cleanup_scheduler(
    max_age_minutes: int,
    interval_minutes: int = 30
) -> None:
    """
    Start background scheduler for automatic cleanup.

    Args:
        max_age_minutes: Maximum age of files to keep
        interval_minutes: How often to run cleanup (default: 30 minutes)
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Cleanup scheduler already running")
        return

    if AsyncIOScheduler is None:
        raise ImportError("apscheduler not installed")

    # Create scheduler
    _scheduler = AsyncIOScheduler()

    # Add cleanup job
    _scheduler.add_job(
        func=lambda: cleanup_old_audio_files(max_age_minutes),
        trigger="interval",
        minutes=interval_minutes,
        id="audio_cleanup",
        name="Clean up old audio files",
        replace_existing=True
    )

    # Start scheduler
    _scheduler.start()
    logger.info(
        f"Cleanup scheduler started: running every {interval_minutes} minutes, "
        f"deleting files older than {max_age_minutes} minutes"
    )


async def stop_cleanup_scheduler() -> None:
    """
    Stop the cleanup scheduler gracefully.
    """
    global _scheduler

    if _scheduler is None:
        logger.warning("Cleanup scheduler not running")
        return

    _scheduler.shutdown(wait=True)
    _scheduler = None
    logger.info("Cleanup scheduler stopped")


# Utility Functions
def get_directory_stats() -> dict:
    """
    Get statistics about the audio directory.

    Returns:
        Dictionary with file counts and sizes
    """
    if not AUDIO_DIR.exists():
        return {
            "exists": False,
            "file_count": 0,
            "total_size_bytes": 0
        }

    mp3_files = [f for f in AUDIO_DIR.iterdir() if f.is_file() and f.suffix == ".mp3"]

    total_size = sum(f.stat().st_size for f in mp3_files)

    return {
        "exists": True,
        "file_count": len(mp3_files),
        "total_size_bytes": total_size,
        "total_size_mb": total_size / (1024 * 1024)
    }


async def cleanup_all_audio_files() -> CleanupStats:
    """
    Delete ALL audio files (regardless of age).

    Useful for testing or emergency cleanup.

    Returns:
        CleanupStats with operation results
    """
    return await cleanup_old_audio_files(max_age_minutes=0)


def get_oldest_file_age_minutes() -> Optional[float]:
    """
    Get the age of the oldest MP3 file in minutes.

    Returns:
        Age in minutes, or None if no files exist
    """
    if not AUDIO_DIR.exists():
        return None

    mp3_files = [f for f in AUDIO_DIR.iterdir() if f.is_file() and f.suffix == ".mp3"]

    if not mp3_files:
        return None

    current_time = time.time()
    oldest_mtime = min(f.stat().st_mtime for f in mp3_files)
    age_seconds = current_time - oldest_mtime

    return age_seconds / 60
