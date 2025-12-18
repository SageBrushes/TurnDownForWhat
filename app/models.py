"""Pydantic models for API requests and responses."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TTSRequest(BaseModel):
    """Request model for TTS generation."""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to convert to speech")
    voice: str = Field(..., min_length=1, description="Voice ID or name to use")
    speaker_ips: List[str] = Field(..., min_length=1, description="List of speaker IP addresses")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Ensure text is not just whitespace."""
        if not v.strip():
            raise ValueError("Text cannot be empty or just whitespace")
        return v.strip()

    @field_validator("voice")
    @classmethod
    def validate_voice(cls, v: str) -> str:
        """Ensure voice is not just whitespace."""
        if not v.strip():
            raise ValueError("Voice cannot be empty or just whitespace")
        return v.strip()

    @field_validator("speaker_ips")
    @classmethod
    def validate_speaker_ips(cls, v: List[str]) -> List[str]:
        """Ensure speaker IPs are valid."""
        if not v:
            raise ValueError("At least one speaker IP is required")
        # Basic validation that they're not empty
        for ip in v:
            if not ip or not ip.strip():
                raise ValueError("Speaker IP cannot be empty")
        return [ip.strip() for ip in v]


class TTSResponse(BaseModel):
    """Response model for TTS generation."""
    audio_url: str = Field(..., description="URL to the generated audio file")
    filename: str = Field(..., description="Filename of the generated audio")
    text: str = Field(..., description="The text that was converted to speech")
    voice: str = Field(..., description="Voice that was used")
    speaker_ips: List[str] = Field(..., description="Speakers where audio is playing")
    duration: Optional[float] = Field(None, description="Audio duration in seconds (if available)")


class TTSPlaybackRequest(BaseModel):
    """Request model for replaying existing TTS audio."""
    filename: str = Field(..., min_length=1, description="Filename of the audio to play")
    speaker_ips: List[str] = Field(..., min_length=1, description="List of speaker IP addresses")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Ensure filename is valid and safe."""
        if not v.strip():
            raise ValueError("Filename cannot be empty")
        # Security: Prevent path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Invalid filename: contains path separators")
        if not v.endswith(".mp3"):
            raise ValueError("Invalid filename: must be an MP3 file")
        return v.strip()

    @field_validator("speaker_ips")
    @classmethod
    def validate_speaker_ips(cls, v: List[str]) -> List[str]:
        """Ensure speaker IPs are valid."""
        if not v:
            raise ValueError("At least one speaker IP is required")
        for ip in v:
            if not ip or not ip.strip():
                raise ValueError("Speaker IP cannot be empty")
        return [ip.strip() for ip in v]


class TTSPlaybackResponse(BaseModel):
    """Response model for TTS playback."""
    audio_url: str = Field(..., description="URL of the audio being played")
    filename: str = Field(..., description="Filename of the audio")
    speaker_ips: List[str] = Field(..., description="Speakers where audio is playing")
    message: str = Field(..., description="Status message")


class VoiceInfo(BaseModel):
    """Model for voice information."""
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Display name of the voice")
    category: str = Field(..., description="Voice category (e.g., 'premade')")
    labels: Dict[str, Any] = Field(default_factory=dict, description="Voice metadata")


class VoicesResponse(BaseModel):
    """Response model for available voices."""
    voices: List[VoiceInfo] = Field(..., description="List of available voices")
    count: int = Field(..., description="Number of voices available")
