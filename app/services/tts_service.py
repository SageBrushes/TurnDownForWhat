"""
TTS Service - ElevenLabs Integration

Handles text-to-speech generation, voice management, and audio URL construction.
Implements async operations for non-blocking API calls.
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import re

try:
    from elevenlabs.client import ElevenLabs, Voice as ElevenLabsVoice
except ImportError:
    # Allow imports during testing when elevenlabs may not be installed
    ElevenLabs = None
    ElevenLabsVoice = None


# Configuration
AUDIO_DIR = Path(__file__).parent.parent.parent / "static" / "audio"
MAX_TEXT_LENGTH = 5000  # ElevenLabs has limits, being conservative
DEFAULT_PORT = 8000


# Models
class Voice(BaseModel):
    """Voice model for API responses."""
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Display name of the voice")
    category: str = Field(..., description="Voice category (e.g., 'premade')")
    labels: Dict[str, Any] = Field(default_factory=dict, description="Voice metadata")


# Custom Exceptions
class TTSError(Exception):
    """Base exception for TTS operations."""
    pass


class InvalidAPIKeyError(TTSError):
    """Raised when API key is invalid or missing."""
    pass


class RateLimitError(TTSError):
    """Raised when API rate limit is exceeded."""
    pass


# Core Functions
async def generate_tts_audio(
    text: str,
    voice: str,
    api_key: str,
    model: str = "eleven_turbo_v2_5"  # Free tier compatible model
) -> str:
    """
    Generate TTS audio and save to file.

    Args:
        text: Text to convert to speech
        voice: Voice name or ID to use
        api_key: ElevenLabs API key
        model: TTS model to use

    Returns:
        Filename of the generated audio file (e.g., "abc123.mp3")

    Raises:
        ValueError: If text is empty or too long
        InvalidAPIKeyError: If API key is invalid or missing
        RateLimitError: If API rate limit exceeded
        TTSError: For other API errors
    """
    # Validate inputs
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Text too long. Maximum length is {MAX_TEXT_LENGTH} characters")

    if not api_key or not api_key.strip():
        raise InvalidAPIKeyError("API key is required")

    # Ensure audio directory exists
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Run ElevenLabs API call in thread pool (it's synchronous)
        def _generate_audio():
            """Synchronous function to call ElevenLabs API."""
            client = ElevenLabs(api_key=api_key)

            # Generate audio
            audio_generator = client.generate(
                text=text,
                voice=voice,
                model=model
            )

            # Collect audio bytes
            audio_bytes = b""
            for chunk in audio_generator:
                audio_bytes += chunk

            return audio_bytes

        # Run in thread pool to avoid blocking
        audio_bytes = await asyncio.to_thread(_generate_audio)

        # Generate unique filename
        filename = f"{uuid.uuid4()}.mp3"
        file_path = AUDIO_DIR / filename

        # Save to file
        await asyncio.to_thread(file_path.write_bytes, audio_bytes)

        return filename

    except Exception as e:
        error_msg = str(e).lower()

        # Classify the error
        if "api key" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
            raise InvalidAPIKeyError(f"Invalid API key: {e}")
        elif "rate limit" in error_msg or "quota" in error_msg or "too many" in error_msg:
            raise RateLimitError(f"Rate limit exceeded: {e}")
        else:
            raise TTSError(f"TTS generation failed: {e}")


async def get_available_voices(api_key: str) -> List[Voice]:
    """
    Get list of available voices from ElevenLabs.

    Args:
        api_key: ElevenLabs API key

    Returns:
        List of Voice objects

    Raises:
        InvalidAPIKeyError: If API key is invalid
        TTSError: For other API errors
    """
    if not api_key or not api_key.strip():
        raise InvalidAPIKeyError("API key is required")

    try:
        def _get_voices():
            """Synchronous function to get voices."""
            import requests

            # Use direct API call to avoid SDK Pydantic validation issues
            headers = {"xi-api-key": api_key}
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers=headers,
                timeout=10
            )

            if response.status_code == 401:
                raise InvalidAPIKeyError("Invalid API key")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code != 200:
                raise TTSError(f"API error: {response.status_code}")

            data = response.json()
            return data.get('voices', [])

        # Run in thread pool
        voices_data = await asyncio.to_thread(_get_voices)

        # Convert to our Voice model
        voice_list = []
        for v in voices_data:
            voice_list.append(
                Voice(
                    voice_id=v.get('voice_id', ''),
                    name=v.get('name', 'Unknown'),
                    category=v.get('category', ''),
                    labels=v.get('labels', {})
                )
            )

        return voice_list

    except Exception as e:
        error_msg = str(e).lower()

        if "api key" in error_msg or "unauthorized" in error_msg:
            raise InvalidAPIKeyError(f"Invalid API key: {e}")
        else:
            raise TTSError(f"Failed to fetch voices: {e}")


def get_audio_url(
    filename: str,
    local_ip: str,
    port: int = DEFAULT_PORT
) -> str:
    """
    Build complete audio URL for Sonos playback.

    Sonos requires complete file URLs, not streaming endpoints.

    Args:
        filename: Audio filename (e.g., "abc123.mp3")
        local_ip: Local IP address of the server
        port: Server port (default: 8000)

    Returns:
        Complete HTTP URL (e.g., "http://192.168.1.100:8000/static/audio/abc123.mp3")

    Raises:
        ValueError: If filename or IP is invalid
    """
    # Validate filename
    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")

    # Security: Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid filename: contains path separators")

    # Validate IP address
    if not local_ip or not local_ip.strip():
        raise ValueError("IP address cannot be empty")

    # Basic IP format validation
    ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(ip_pattern, local_ip):
        raise ValueError(f"Invalid IP address format: {local_ip}")

    # Build URL
    url = f"http://{local_ip}:{port}/static/audio/{filename}"
    return url


# Utility Functions
def validate_text_length(text: str) -> bool:
    """
    Check if text is within acceptable length.

    Args:
        text: Text to validate

    Returns:
        True if valid, False otherwise
    """
    return 0 < len(text) <= MAX_TEXT_LENGTH


def sanitize_text(text: str) -> str:
    """
    Sanitize text for TTS generation.

    Removes excessive whitespace and control characters.

    Args:
        text: Raw text input

    Returns:
        Sanitized text
    """
    # Remove control characters except newlines and tabs
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize whitespace
    text = " ".join(text.split())

    return text.strip()
