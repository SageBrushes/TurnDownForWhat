"""Speaker API endpoints for controlling Sonos speakers."""
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any

from app.models import (
    VolumeRequest,
    FadeRequest,
    VolumeResponse,
    FadeResponse,
    PlaybackResponse,
    SpeakerInfo,
    SpeakerStatus,
    SetAllVolumesRequest,
    SetAllVolumesResponse,
)
from app.services import sonos_service
from app.services.websocket_manager import get_connection_manager, create_speaker_update_message, create_fade_progress_message
from app.utils.errors import create_error_response, ErrorCode, error_response


router = APIRouter(prefix="/api/speakers", tags=["speakers"])


@router.get("", response_model=List[SpeakerInfo])
async def list_speakers():
    """
    List all discovered Sonos speakers.

    Returns a list of all speakers found on the network with their basic info.
    Uses caching to avoid repeated network scans.

    Returns:
        List of speaker objects with ip, name, volume, is_coordinator
    """
    try:
        speakers = await sonos_service.discover_speakers()
        return speakers
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to discover speakers: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.get("/{ip}/status", response_model=SpeakerStatus)
async def get_speaker_status(ip: str):
    """
    Get detailed status for a specific speaker.

    Args:
        ip: Speaker IP address

    Returns:
        Detailed speaker status including transport state, current track, etc.

    Raises:
        503: Speaker is unreachable
    """
    try:
        status_data = await sonos_service.get_speaker_status(ip)
        return status_data
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to get speaker status: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/{ip}/volume", response_model=VolumeResponse)
async def set_speaker_volume(ip: str, request: VolumeRequest):
    """
    Set speaker volume instantly (no fade).

    Args:
        ip: Speaker IP address
        request: Volume request with target volume (0-100)

    Returns:
        Volume response with ip, volume, and success message

    Raises:
        400: Invalid volume
        503: Speaker is unreachable
    """
    try:
        result = await sonos_service.set_speaker_volume(ip, request.volume)

        # Broadcast update via WebSocket
        try:
            manager = get_connection_manager()
            await manager.broadcast(create_speaker_update_message(ip, {"volume": request.volume}))
        except Exception:
            # Don't fail the request if WebSocket broadcast fails
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to set volume: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/{ip}/fade", response_model=FadeResponse)
async def fade_speaker_volume(ip: str, request: FadeRequest):
    """
    Fade speaker volume smoothly to target using S-curve algorithm.

    Broadcasts progress updates via WebSocket during the fade operation.

    Args:
        ip: Speaker IP address
        request: Fade request with target_volume (0-100)

    Returns:
        Fade response with ip, volume, direction, steps, duration, message

    Raises:
        400: Invalid volume
        409: Another fade operation is already in progress on this speaker
        503: Speaker is unreachable
    """
    manager = get_connection_manager()

    # Define progress callback for WebSocket broadcasting
    async def progress_callback(current_step: int, total_steps: int):
        """Broadcast fade progress via WebSocket."""
        try:
            progress_percent = int((current_step / total_steps) * 100)
            await manager.broadcast(
                create_fade_progress_message(ip, current_step, total_steps, progress_percent)
            )
        except Exception:
            # Don't let broadcast errors break the fade
            pass

    try:
        result = await sonos_service.fade_speaker_volume(
            ip,
            request.target_volume,
            callback=progress_callback
        )

        # Broadcast final update
        try:
            await manager.broadcast(create_speaker_update_message(ip, {"volume": request.target_volume}))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to fade volume: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/{ip}/play", response_model=PlaybackResponse)
async def play_speaker(ip: str):
    """
    Resume/play speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Playback response with ip and success message

    Raises:
        503: Speaker is unreachable
    """
    try:
        result = await sonos_service.play_speaker(ip)

        # Broadcast update via WebSocket
        try:
            manager = get_connection_manager()
            await manager.broadcast(create_speaker_update_message(ip, {"is_playing": True}))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to play speaker: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/{ip}/pause", response_model=PlaybackResponse)
async def pause_speaker(ip: str):
    """
    Pause speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Playback response with ip and success message

    Raises:
        503: Speaker is unreachable
    """
    try:
        result = await sonos_service.pause_speaker(ip)

        # Broadcast update via WebSocket
        try:
            manager = get_connection_manager()
            await manager.broadcast(create_speaker_update_message(ip, {"is_playing": False, "is_paused": True}))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to pause speaker: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/{ip}/stop", response_model=PlaybackResponse)
async def stop_speaker(ip: str):
    """
    Stop speaker playback.

    Args:
        ip: Speaker IP address

    Returns:
        Playback response with ip and success message

    Raises:
        503: Speaker is unreachable
    """
    try:
        result = await sonos_service.stop_speaker(ip)

        # Broadcast update via WebSocket
        try:
            manager = get_connection_manager()
            await manager.broadcast(create_speaker_update_message(ip, {"is_playing": False, "is_stopped": True}))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to stop speaker: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )


@router.post("/volume/all", response_model=SetAllVolumesResponse)
async def set_all_speakers_volume(request: SetAllVolumesRequest):
    """
    Set volume on all discovered speakers.

    Args:
        request: Request with target volume (0-100)

    Returns:
        Response with success/failure counts and individual results

    Raises:
        400: Invalid volume
    """
    try:
        result = await sonos_service.set_all_speakers_volume(request.volume)

        # Broadcast update via WebSocket for all speakers
        try:
            manager = get_connection_manager()
            for speaker_result in result["results"]:
                if "ip" in speaker_result:
                    await manager.broadcast(
                        create_speaker_update_message(speaker_result["ip"], {"volume": request.volume})
                    )
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to set all volumes: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR
        )
