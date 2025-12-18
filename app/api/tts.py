"""
TTS API Endpoints

FastAPI routes for text-to-speech generation, voice management, and audio playback.
Integrates with ElevenLabs TTS service and Sonos speaker control.
"""

import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models import (
    TTSRequest,
    TTSResponse,
    TTSPlaybackRequest,
    TTSPlaybackResponse,
    VoicesResponse,
    VoiceInfo
)
from app.services import tts_service
from app.services.websocket_manager import ConnectionManager
from app.services.tts_service import TTSError, InvalidAPIKeyError, RateLimitError
from app.utils.network import get_local_ip
from app.utils.errors import ErrorCode
from app.config import settings

# Import sonos_service - will be available after Package B is merged
try:
    from app.services import sonos_service
except ImportError:
    # Placeholder for testing before sonos_service is implemented
    sonos_service = None


logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/api/tts", tags=["tts"])

# Audio directory
AUDIO_DIR = Path(__file__).parent.parent.parent / "static" / "audio"


def get_connection_manager() -> ConnectionManager:
    """Get WebSocket connection manager singleton."""
    return ConnectionManager()


@router.post("/generate", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """
    Generate TTS audio and play on selected speakers.

    Steps:
    1. Generate TTS audio using ElevenLabs
    2. Build audio URL for Sonos playback
    3. Play audio on all specified speakers
    4. Broadcast WebSocket event to connected clients

    Args:
        request: TTSRequest with text, voice, and speaker IPs

    Returns:
        TTSResponse with audio URL, filename, and metadata

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 429: Rate limit exceeded
        HTTPException 500: TTS generation error
        HTTPException 503: Speaker unreachable
    """
    logger.info(f"Generating TTS for text: '{request.text[:50]}...' with voice: {request.voice}")

    try:
        # 1. Generate TTS audio
        filename = await tts_service.generate_tts_audio(
            text=request.text,
            voice=request.voice,
            api_key=settings.ELEVENLABS_API_KEY
        )
        logger.info(f"TTS audio generated: {filename}")

        # 2. Build audio URL
        local_ip = get_local_ip()
        audio_url = tts_service.get_audio_url(
            filename=filename,
            local_ip=local_ip,
            port=settings.PORT
        )
        logger.info(f"Audio URL: {audio_url}")

        # 3. Play on speakers
        if sonos_service is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": ErrorCode.SERVICE_UNAVAILABLE.value,
                    "message": "Sonos service not available"
                }
            )

        for speaker_ip in request.speaker_ips:
            try:
                await sonos_service.play_uri(speaker_ip, audio_url)
                logger.info(f"Playing on speaker {speaker_ip}")
            except HTTPException as e:
                # Re-raise speaker errors
                logger.error(f"Failed to play on speaker {speaker_ip}: {e.detail}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error playing on speaker {speaker_ip}: {e}")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error_code": ErrorCode.SPEAKER_UNREACHABLE.value,
                        "message": f"Cannot connect to speaker {speaker_ip}: {str(e)}"
                    }
                )

        # 4. Broadcast WebSocket event
        ws_manager = get_connection_manager()
        for speaker_ip in request.speaker_ips:
            await ws_manager.broadcast({
                "type": "tts_started",
                "data": {
                    "text": request.text,
                    "speaker_ip": speaker_ip,
                    "audio_url": audio_url,
                    "filename": filename,
                    "voice": request.voice
                }
            })

        logger.info(f"TTS generation successful for {len(request.speaker_ips)} speaker(s)")

        return TTSResponse(
            audio_url=audio_url,
            filename=filename,
            text=request.text,
            voice=request.voice,
            speaker_ips=request.speaker_ips,
            duration=None  # Could be calculated from audio file if needed
        )

    except InvalidAPIKeyError as e:
        logger.error(f"Invalid API key: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": ErrorCode.INVALID_API_KEY.value,
                "message": str(e)
            }
        )
    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}")
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": ErrorCode.RATE_LIMIT_EXCEEDED.value,
                "message": str(e)
            }
        )
    except TTSError as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.TTS_ERROR.value,
                "message": str(e)
            }
        )
    except HTTPException:
        # Re-raise HTTPExceptions (like speaker errors)
        raise
    except Exception as e:
        logger.exception(f"Unexpected error generating TTS: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": f"Internal server error: {str(e)}"
            }
        )


@router.get("/voices", response_model=VoicesResponse)
async def get_voices():
    """
    Get list of available ElevenLabs voices.

    Returns:
        VoicesResponse with list of available voices and count

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 500: Service error
    """
    logger.info("Fetching available voices")

    try:
        voices = await tts_service.get_available_voices(
            api_key=settings.ELEVENLABS_API_KEY
        )

        # Convert to VoiceInfo models
        voice_list = [
            VoiceInfo(
                voice_id=v.voice_id,
                name=v.name,
                category=v.category,
                labels=v.labels
            )
            for v in voices
        ]

        logger.info(f"Retrieved {len(voice_list)} voices")

        return VoicesResponse(
            voices=voice_list,
            count=len(voice_list)
        )

    except InvalidAPIKeyError as e:
        logger.error(f"Invalid API key: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": ErrorCode.INVALID_API_KEY.value,
                "message": str(e)
            }
        )
    except TTSError as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.TTS_ERROR.value,
                "message": str(e)
            }
        )
    except Exception as e:
        logger.exception(f"Unexpected error fetching voices: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": f"Internal server error: {str(e)}"
            }
        )


@router.post("/play", response_model=TTSPlaybackResponse)
async def play_existing_tts(request: TTSPlaybackRequest):
    """
    Replay existing TTS audio file on selected speakers.

    Args:
        request: TTSPlaybackRequest with filename and speaker IPs

    Returns:
        TTSPlaybackResponse with audio URL and playback status

    Raises:
        HTTPException 404: Audio file not found
        HTTPException 503: Speaker unreachable
    """
    logger.info(f"Playing existing audio: {request.filename} on {len(request.speaker_ips)} speaker(s)")

    # Check if file exists
    audio_file = AUDIO_DIR / request.filename
    if not audio_file.exists():
        logger.error(f"Audio file not found: {request.filename}")
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.FILE_NOT_FOUND.value,
                "message": f"Audio file not found: {request.filename}"
            }
        )

    try:
        # Build audio URL
        local_ip = get_local_ip()
        audio_url = tts_service.get_audio_url(
            filename=request.filename,
            local_ip=local_ip,
            port=settings.PORT
        )

        # Play on speakers
        if sonos_service is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": ErrorCode.SERVICE_UNAVAILABLE.value,
                    "message": "Sonos service not available"
                }
            )

        for speaker_ip in request.speaker_ips:
            try:
                await sonos_service.play_uri(speaker_ip, audio_url)
                logger.info(f"Playing on speaker {speaker_ip}")
            except HTTPException as e:
                logger.error(f"Failed to play on speaker {speaker_ip}: {e.detail}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error playing on speaker {speaker_ip}: {e}")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error_code": ErrorCode.SPEAKER_UNREACHABLE.value,
                        "message": f"Cannot connect to speaker {speaker_ip}: {str(e)}"
                    }
                )

        # Broadcast WebSocket event
        ws_manager = get_connection_manager()
        for speaker_ip in request.speaker_ips:
            await ws_manager.broadcast({
                "type": "tts_started",
                "data": {
                    "text": f"Replaying: {request.filename}",
                    "speaker_ip": speaker_ip,
                    "audio_url": audio_url,
                    "filename": request.filename
                }
            })

        logger.info(f"Successfully playing {request.filename} on {len(request.speaker_ips)} speaker(s)")

        return TTSPlaybackResponse(
            audio_url=audio_url,
            filename=request.filename,
            speaker_ips=request.speaker_ips,
            message=f"Playing {request.filename} on {len(request.speaker_ips)} speaker(s)"
        )

    except HTTPException:
        # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.exception(f"Unexpected error playing existing audio: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": f"Internal server error: {str(e)}"
            }
        )
