"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


# ============ Speaker Models ============

# Request Models
class VolumeRequest(BaseModel):
    """Request model for setting speaker volume."""
    volume: int = Field(..., ge=0, le=100, description="Target volume (0-100)")

    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v: int) -> int:
        """Ensure volume is within valid range."""
        if v < 0 or v > 100:
            raise ValueError("Volume must be between 0 and 100")
        return v


class FadeRequest(BaseModel):
    """Request model for fading speaker volume."""
    target_volume: int = Field(..., ge=0, le=100, description="Target volume to fade to (0-100)")

    @field_validator('target_volume')
    @classmethod
    def validate_target_volume(cls, v: int) -> int:
        """Ensure target volume is within valid range."""
        if v < 0 or v > 100:
            raise ValueError("Target volume must be between 0 and 100")
        return v


class SetAllVolumesRequest(BaseModel):
    """Request model for setting volume on all speakers."""
    volume: int = Field(..., ge=0, le=100, description="Target volume for all speakers (0-100)")

    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v: int) -> int:
        """Ensure volume is within valid range."""
        if v < 0 or v > 100:
            raise ValueError("Volume must be between 0 and 100")
        return v


# Response Models
class SpeakerInfo(BaseModel):
    """Basic speaker information."""
    ip: str = Field(..., description="Speaker IP address")
    name: str = Field(..., description="Speaker name")
    volume: int = Field(..., ge=0, le=100, description="Current volume")
    is_coordinator: bool = Field(..., description="Whether speaker is a coordinator")


class CurrentTrack(BaseModel):
    """Information about the currently playing track."""
    title: str = Field(default="", description="Track title")
    artist: str = Field(default="", description="Track artist")
    album: str = Field(default="", description="Track album")


class SpeakerStatus(BaseModel):
    """Detailed speaker status."""
    ip: str = Field(..., description="Speaker IP address")
    name: str = Field(..., description="Speaker name")
    volume: int = Field(..., ge=0, le=100, description="Current volume")
    transport_state: str = Field(..., description="Transport state (PLAYING, PAUSED_PLAYBACK, STOPPED)")
    is_playing: bool = Field(..., description="Whether speaker is currently playing")
    is_paused: bool = Field(..., description="Whether speaker is paused")
    is_stopped: bool = Field(..., description="Whether speaker is stopped")
    current_track: CurrentTrack = Field(..., description="Current track information")


class VolumeResponse(BaseModel):
    """Response for volume operations."""
    ip: str = Field(..., description="Speaker IP address")
    volume: int = Field(..., ge=0, le=100, description="Current/target volume")
    message: str = Field(..., description="Success message")


class FadeResponse(BaseModel):
    """Response for fade operations."""
    ip: str = Field(..., description="Speaker IP address")
    volume: int = Field(..., ge=0, le=100, description="Target volume")
    direction: str = Field(..., description="Fade direction (up, down, none)")
    steps: int = Field(..., ge=0, description="Number of steps taken")
    duration: Optional[float] = Field(None, description="Fade duration in seconds")
    message: str = Field(..., description="Success message")


class PlaybackResponse(BaseModel):
    """Response for playback control operations."""
    ip: str = Field(..., description="Speaker IP address")
    message: str = Field(..., description="Success message")


class PlayUriResponse(BaseModel):
    """Response for play URI operations."""
    ip: str = Field(..., description="Speaker IP address")
    uri: str = Field(..., description="Audio URI that was played")
    message: str = Field(..., description="Success message")


class SetAllVolumesResponse(BaseModel):
    """Response for setting volume on all speakers."""
    success_count: int = Field(..., ge=0, description="Number of speakers successfully updated")
    failed_count: int = Field(..., ge=0, description="Number of speakers that failed")
    results: List[Dict[str, Any]] = Field(..., description="Individual results for each speaker")
    message: str = Field(..., description="Summary message")


class SpeakerListResponse(BaseModel):
    """Response for listing all speakers."""
    speakers: List[SpeakerInfo] = Field(..., description="List of discovered speakers")
    count: int = Field(..., ge=0, description="Number of speakers discovered")


# ============ TTS Models ============

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
