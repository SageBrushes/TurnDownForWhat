"""Sonos service layer for async speaker operations."""
import asyncio
import math
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import soco
from soco import SoCo

from app.utils.async_helpers import run_in_thread
from app.utils.errors import (
    speaker_unreachable_error,
    invalid_volume_error,
    concurrent_operation_error,
)


# Speaker discovery cache
_speaker_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamp: Optional[datetime] = None
_cache_lock = asyncio.Lock()
_speaker_locks: Dict[str, asyncio.Lock] = {}

# Constants
DISCOVERY_CACHE_DURATION = timedelta(minutes=5)
FADE_STEPS = 10  # Minimum steps for smooth fade
FADE_BASE_SLEEP = 0.3  # Base sleep time between steps


async def discover_speakers(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Discover all Sonos speakers on the network with caching.

    Args:
        force_refresh: If True, bypass cache and force new discovery

    Returns:
        List of speaker information dictionaries with keys:
        - ip: Speaker IP address
        - name: Speaker name
        - volume: Current volume (0-100)
        - is_coordinator: Whether this is a group coordinator

    Raises:
        Exception: If discovery fails
    """
    global _speaker_cache, _cache_timestamp

    async with _cache_lock:
        # Check if cache is valid
        if (
            not force_refresh
            and _cache_timestamp
            and datetime.now() - _cache_timestamp < DISCOVERY_CACHE_DURATION
            and _speaker_cache
        ):
            return list(_speaker_cache.values())

        # Perform discovery in thread pool (blocking operation)
        try:
            speakers = await run_in_thread(lambda: list(soco.discover()))

            if not speakers:
                return []

            # Build speaker info list
            speaker_list = []
            for speaker in speakers:
                try:
                    info = {
                        "ip": speaker.ip_address,
                        "name": await run_in_thread(lambda s=speaker: s.player_name),
                        "volume": await run_in_thread(lambda s=speaker: s.volume),
                        "is_coordinator": await run_in_thread(
                            lambda s=speaker: s.is_coordinator
                        ),
                    }
                    speaker_list.append(info)
                    _speaker_cache[info["ip"]] = info
                except Exception as e:
                    # Skip speakers that error during info gathering
                    continue

            _cache_timestamp = datetime.now()
            return speaker_list

        except Exception as e:
            raise Exception(f"Speaker discovery failed: {e}")


async def get_speaker_status(ip: str) -> Dict[str, Any]:
    """
    Get detailed status of a specific speaker.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with speaker status:
        - ip: Speaker IP address
        - name: Speaker name
        - volume: Current volume (0-100)
        - is_playing: Whether speaker is currently playing
        - is_paused: Whether speaker is paused
        - is_stopped: Whether speaker is stopped
        - current_track: Current track info (title, artist, album)
        - transport_state: Raw transport state string

    Raises:
        HTTPException: If speaker is unreachable
    """
    try:
        speaker = SoCo(ip)

        # Get transport info
        transport_info = await run_in_thread(speaker.get_current_transport_info)
        transport_state = transport_info.get("current_transport_state", "STOPPED")

        # Get track info
        track_info = await run_in_thread(speaker.get_current_track_info)

        # Get speaker properties
        name = await run_in_thread(lambda: speaker.player_name)
        volume = await run_in_thread(lambda: speaker.volume)

        return {
            "ip": ip,
            "name": name,
            "volume": volume,
            "is_playing": transport_state == "PLAYING",
            "is_paused": transport_state == "PAUSED_PLAYBACK",
            "is_stopped": transport_state == "STOPPED",
            "current_track": {
                "title": track_info.get("title", ""),
                "artist": track_info.get("artist", ""),
                "album": track_info.get("album", ""),
            },
            "transport_state": transport_state,
        }
    except Exception as e:
        raise speaker_unreachable_error(ip)


async def set_speaker_volume(ip: str, volume: int) -> Dict[str, Any]:
    """
    Set speaker volume instantly (no fade).

    Args:
        ip: Speaker IP address
        volume: Target volume (0-100)

    Returns:
        Dictionary with updated speaker info

    Raises:
        HTTPException: If speaker is unreachable or volume is invalid
    """
    if not 0 <= volume <= 100:
        raise invalid_volume_error(volume)

    try:
        speaker = SoCo(ip)
        await run_in_thread(lambda: setattr(speaker, "volume", volume))

        return {
            "ip": ip,
            "volume": volume,
            "message": f"Volume set to {volume}",
        }
    except Exception as e:
        raise speaker_unreachable_error(ip)


async def fade_speaker_volume(
    ip: str,
    target_volume: int,
    callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Fade speaker volume using smooth S-curve algorithm from original script.

    This function uses a sigmoid-like (ease-in-out) curve for natural volume transitions.
    The fade is faster in the middle and slower at the start/end for a smoother feel.

    Args:
        ip: Speaker IP address
        target_volume: Target volume (0-100)
        callback: Optional callback function called with (current_step, total_steps)
                  for progress updates (useful for WebSocket broadcasting)

    Returns:
        Dictionary with fade completion info

    Raises:
        HTTPException: If speaker is unreachable, volume is invalid,
                      or another fade is in progress
    """
    if not 0 <= target_volume <= 100:
        raise invalid_volume_error(target_volume)

    # Acquire lock for this speaker to prevent concurrent fades
    if ip not in _speaker_locks:
        _speaker_locks[ip] = asyncio.Lock()

    if _speaker_locks[ip].locked():
        raise concurrent_operation_error(f"speaker {ip}")

    async with _speaker_locks[ip]:
        try:
            speaker = SoCo(ip)
            current_volume = await run_in_thread(lambda: speaker.volume)

            # If already at target, no fade needed
            if current_volume == target_volume:
                return {
                    "ip": ip,
                    "volume": target_volume,
                    "message": f"Already at target volume {target_volume}",
                }

            # Calculate fade parameters
            volume_difference = abs(target_volume - current_volume)
            steps = max(volume_difference, FADE_STEPS)  # Minimum steps for smoothness
            fade_direction = "up" if current_volume < target_volume else "down"

            # Execute fade with S-curve algorithm
            for step in range(steps + 1):
                # Progress through the fade (0.0 to 1.0)
                progress = step / steps

                # Use smooth S-curve (sigmoid-like) for natural fade
                # Formula: 0.5 * (1 + sin(π * (progress - 0.5)))
                # This creates ease-in-out effect
                smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))

                # Calculate volume based on smooth progress
                if fade_direction == "up":
                    vol = int(
                        current_volume
                        + (target_volume - current_volume) * smooth_progress
                    )
                else:
                    vol = int(
                        current_volume
                        - (current_volume - target_volume) * smooth_progress
                    )

                # Ensure volume stays within bounds
                vol = max(0, min(100, vol))

                # Set volume (blocking operation, run in thread)
                await run_in_thread(lambda v=vol: setattr(speaker, "volume", v))

                # Call progress callback if provided
                if callback:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(step + 1, steps + 1)
                        else:
                            callback(step + 1, steps + 1)
                    except Exception:
                        # Don't let callback errors break the fade
                        pass

                # Variable sleep time - faster in middle, slower at start/end
                # This creates a more natural feeling fade
                sleep_factor = 1.0 - 0.5 * math.sin(math.pi * progress)
                await asyncio.sleep(FADE_BASE_SLEEP * sleep_factor)

            return {
                "ip": ip,
                "volume": target_volume,
                "steps": steps + 1,
                "direction": fade_direction,
                "message": f"Volume faded to {target_volume}",
            }

        except asyncio.CancelledError:
            # Handle task cancellation (e.g., user stops fade)
            raise
        except Exception as e:
            raise speaker_unreachable_error(ip)


async def play_uri(ip: str, uri: str) -> Dict[str, Any]:
    """
    Play audio from a URI on the speaker.

    Args:
        ip: Speaker IP address
        uri: Audio URI (complete URL to audio file)

    Returns:
        Dictionary with playback status

    Raises:
        HTTPException: If speaker is unreachable
    """
    try:
        speaker = SoCo(ip)

        # Clear queue and play URI
        await run_in_thread(speaker.clear_queue)
        await run_in_thread(lambda: speaker.play_uri(uri))

        return {
            "ip": ip,
            "uri": uri,
            "message": "Playing audio",
        }
    except Exception as e:
        raise speaker_unreachable_error(ip)


async def pause_speaker(ip: str) -> Dict[str, Any]:
    """
    Pause playback on speaker.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with pause status

    Raises:
        HTTPException: If speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.pause)

        return {
            "ip": ip,
            "message": "Playback paused",
        }
    except Exception as e:
        raise speaker_unreachable_error(ip)


async def stop_speaker(ip: str) -> Dict[str, Any]:
    """
    Stop playback on speaker.

    Args:
        ip: Speaker IP address

    Returns:
        Dictionary with stop status

    Raises:
        HTTPException: If speaker is unreachable
    """
    try:
        speaker = SoCo(ip)
        await run_in_thread(speaker.stop)

        return {
            "ip": ip,
            "message": "Playback stopped",
        }
    except Exception as e:
        raise speaker_unreachable_error(ip)


async def clear_speaker_cache() -> None:
    """Clear the speaker discovery cache to force refresh on next discovery."""
    global _speaker_cache, _cache_timestamp
    async with _cache_lock:
        _speaker_cache.clear()
        _cache_timestamp = None
