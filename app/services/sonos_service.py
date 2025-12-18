"""Sonos Service Layer - Async operations for speaker control."""
import asyncio
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from soco import SoCo
import soco
from fastapi import HTTPException

from app.utils.errors import (
    ErrorCode,
    speaker_unreachable_error,
    invalid_volume_error,
    concurrent_operation_error,
)
from app.utils.async_helpers import run_in_thread


# Configuration constants
CACHE_TIMEOUT_MINUTES = 5
FADE_STEPS = 100  # Minimum steps for smooth fading
FADE_BASE_SLEEP = 0.05  # Base sleep time between volume changes (seconds)

# Module-level cache for speaker discovery
_speaker_cache: List[Dict] = []
_cache_timestamp: Optional[datetime] = None

# Per-speaker locks for fade operations
_speaker_locks: Dict[str, asyncio.Lock] = {}


def _get_speaker_lock(ip: str) -> asyncio.Lock:
    """Get or create a lock for a specific speaker."""
    if ip not in _speaker_locks:
        _speaker_locks[ip] = asyncio.Lock()
    return _speaker_locks[ip]


async def discover_speakers(force_refresh: bool = False) -> List[Dict]:
    """
    Discover all Sonos speakers on the network.

    Uses caching to avoid repeated network scans. Cache expires after
    CACHE_TIMEOUT_MINUTES or can be bypassed with force_refresh.

    Args:
        force_refresh: Bypass cache and force new discovery

    Returns:
        List of speaker dictionaries with ip, name, volume, is_coordinator

    Raises:
        Exception: If discovery fails
    """
    global _speaker_cache, _cache_timestamp

    # Check if we can use cache
    if not force_refresh and _speaker_cache and _cache_timestamp:
        age = datetime.now() - _cache_timestamp
        if age < timedelta(minutes=CACHE_TIMEOUT_MINUTES):
            return _speaker_cache

    # Perform discovery
    try:
        speakers = await run_in_thread(soco.discover)

        if speakers is None:
            speakers = []

        speaker_list = []
        for speaker in speakers:
            try:
                speaker_info = {
                    "ip": speaker.ip_address,
                    "name": speaker.player_name,
                    "volume": speaker.volume,
                    "is_coordinator": speaker.is_coordinator,
                }
                speaker_list.append(speaker_info)
            except Exception:
                # Skip speakers that fail info gathering
                continue

        # Update cache
        _speaker_cache = speaker_list
        _cache_timestamp = datetime.now()

        return speaker_list

    except Exception as e:
        raise Exception(f"Speaker discovery failed: {str(e)}")


async def clear_speaker_cache() -> None:
    """Clear the speaker discovery cache."""
    global _speaker_cache, _cache_timestamp
    _speaker_cache = []
    _cache_timestamp = None


async def get_speaker_status(ip: str) -> Dict:
    """
    Get detailed status for a specific speaker.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with complete speaker status including:
        - ip, name, volume
        - transport_state (PLAYING, PAUSED_PLAYBACK, STOPPED)
        - is_playing, is_paused, is_stopped flags
        - current_track info (title, artist, album)

    Raises:
        HTTPException: 503 if speaker is unreachable
    """
    try:
        speaker = SoCo(ip)

        # Get transport info
        transport_info = await run_in_thread(speaker.get_current_transport_info)
        transport_state = transport_info.get("current_transport_state", "STOPPED")

        # Get track info
        track_info = await run_in_thread(speaker.get_current_track_info)

        # Get speaker properties (these are synchronous but wrapped for consistency)
        name = await run_in_thread(lambda: speaker.player_name)
        volume = await run_in_thread(lambda: speaker.volume)

        status = {
            "ip": ip,
            "name": name,
            "volume": volume,
            "transport_state": transport_state,
            "is_playing": transport_state == "PLAYING",
            "is_paused": transport_state == "PAUSED_PLAYBACK",
            "is_stopped": transport_state == "STOPPED",
            "current_track": {
                "title": track_info.get("title", ""),
                "artist": track_info.get("artist", ""),
                "album": track_info.get("album", ""),
            }
        }

        return status

    except Exception as e:
        raise speaker_unreachable_error(ip)


async def set_speaker_volume(ip: str, volume: int) -> Dict:
    """
    Set speaker volume instantly (no fade).

    Args:
        ip: Speaker IP address
        volume: Target volume (0-100)

    Returns:
        Dictionary with ip, volume, and success message

    Raises:
        HTTPException: 400 for invalid volume, 503 if unreachable
    """
    # Validate volume
    if volume < 0 or volume > 100:
        raise invalid_volume_error(volume)

    try:
        speaker = SoCo(ip)
        await run_in_thread(lambda: setattr(speaker, 'volume', volume))

        return {
            "ip": ip,
            "volume": volume,
            "message": f"Volume set to {volume}"
        }

    except HTTPException:
        raise
    except Exception:
        raise speaker_unreachable_error(ip)


async def fade_speaker_volume(
    ip: str,
    target_volume: int,
    callback: Optional[Callable[[int, int], Any]] = None
) -> Dict:
    """
    Fade speaker volume smoothly to target using S-curve algorithm.

    Uses per-speaker locking to prevent concurrent fade operations on the
    same speaker, which would cause conflicts.

    Args:
        ip: Speaker IP address
        target_volume: Target volume (0-100)
        callback: Optional progress callback(current_step, total_steps)

    Returns:
        Dictionary with fade results including:
        - ip, volume, direction (up/down)
        - steps taken, duration
        - message

    Raises:
        HTTPException:
            - 400 for invalid volume
            - 409 if another fade is in progress on this speaker
            - 503 if speaker becomes unreachable during fade
    """
    # Validate volume
    if target_volume < 0 or target_volume > 100:
        raise invalid_volume_error(target_volume)

    # Get speaker lock
    lock = _get_speaker_lock(ip)

    # Try to acquire lock (non-blocking)
    if lock.locked():
        raise concurrent_operation_error(f"speaker {ip}")

    async with lock:
        try:
            speaker = SoCo(ip)
            start_volume = await run_in_thread(lambda: speaker.volume)

            # Check if already at target
            if start_volume == target_volume:
                return {
                    "ip": ip,
                    "volume": target_volume,
                    "direction": "none",
                    "steps": 0,
                    "message": f"Already at target volume {target_volume}"
                }

            # Calculate fade parameters
            volume_diff = target_volume - start_volume
            direction = "up" if volume_diff > 0 else "down"

            # Calculate steps (at least FADE_STEPS for smoothness)
            steps = max(abs(volume_diff), FADE_STEPS)

            # S-curve fade using ease-in-out algorithm
            step_count = 0
            start_time = datetime.now()

            total_steps = steps + 1  # Total iterations including start and end
            for i in range(total_steps):
                # Calculate progress (0.0 to 1.0)
                progress = i / steps

                # Apply S-curve (ease-in-out): smooth start and end
                # Using cubic easing: 3*t^2 - 2*t^3
                eased_progress = progress * progress * (3 - 2 * progress)

                # Calculate target volume for this step
                current_volume = start_volume + (volume_diff * eased_progress)
                current_volume = max(0, min(100, int(round(current_volume))))

                # Set volume
                try:
                    await run_in_thread(lambda v=current_volume: setattr(speaker, 'volume', v))
                except Exception:
                    raise speaker_unreachable_error(ip)

                step_count = i + 1

                # Call progress callback if provided
                if callback:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(step_count, total_steps)
                        else:
                            callback(step_count, total_steps)
                    except Exception:
                        # Don't let callback errors break the fade
                        pass

                # Sleep between steps (except on last step)
                if i < steps:
                    await asyncio.sleep(FADE_BASE_SLEEP)

            duration = (datetime.now() - start_time).total_seconds()

            return {
                "ip": ip,
                "volume": target_volume,
                "direction": direction,
                "steps": step_count,
                "duration": round(duration, 2),
                "message": f"Faded volume {direction} to {target_volume} in {step_count} steps"
            }

        except HTTPException:
            raise
        except Exception:
            raise speaker_unreachable_error(ip)


async def play_uri(ip: str, uri: str) -> Dict:
    """
    Play audio from a URI on the speaker.

    Clears the queue before playing to ensure clean playback.

    Args:
        ip: Speaker IP address
        uri: Audio file URI (http://...)

    Returns:
        Dictionary with ip, uri, and success message

    Raises:
        HTTPException: 503 if speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.clear_queue)
        await run_in_thread(lambda: speaker.play_uri(uri))

        return {
            "ip": ip,
            "uri": uri,
            "message": f"Playing audio from {uri}"
        }

    except Exception:
        raise speaker_unreachable_error(ip)


async def pause_speaker(ip: str) -> Dict:
    """
    Pause speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with ip and success message

    Raises:
        HTTPException: 503 if speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.pause)

        return {
            "ip": ip,
            "message": "Playback paused"
        }

    except Exception:
        raise speaker_unreachable_error(ip)


async def stop_speaker(ip: str) -> Dict:
    """
    Stop speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with ip and success message

    Raises:
        HTTPException: 503 if speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.stop)

        return {
            "ip": ip,
            "message": "Playback stopped"
        }

    except Exception:
        raise speaker_unreachable_error(ip)


async def play_speaker(ip: str) -> Dict:
    """
    Resume/play speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with ip and success message

    Raises:
        HTTPException: 503 if speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.play)

        return {
            "ip": ip,
            "message": "Playback resumed"
        }

    except Exception:
        raise speaker_unreachable_error(ip)


async def set_all_speakers_volume(target_volume: int) -> Dict:
    """
    Set volume on all discovered speakers.

    Args:
        target_volume: Target volume (0-100)

    Returns:
        Dictionary with results:
        - success_count: Number of speakers successfully updated
        - failed_count: Number of speakers that failed
        - results: List of individual results

    Raises:
        HTTPException: 400 for invalid volume
    """
    # Validate volume
    if target_volume < 0 or target_volume > 100:
        raise invalid_volume_error(target_volume)

    # Discover all speakers
    speakers = await discover_speakers()

    if not speakers:
        return {
            "success_count": 0,
            "failed_count": 0,
            "results": [],
            "message": "No speakers discovered"
        }

    # Set volume on all speakers concurrently
    tasks = [set_speaker_volume(speaker["ip"], target_volume) for speaker in speakers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count successes and failures
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    failed_count = len(results) - success_count

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": [
            r if not isinstance(r, Exception) else {"error": str(r)}
            for r in results
        ],
        "message": f"Set volume to {target_volume} on {success_count}/{len(speakers)} speakers"
    }
