"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


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


class SetAllVolumesResponse(BaseModel):
    """Response for setting volume on all speakers."""
    success_count: int = Field(..., ge=0, description="Number of speakers successfully updated")
    failed_count: int = Field(..., ge=0, description="Number of speakers that failed")
    results: List[Dict[str, Any]] = Field(..., description="Individual results for each speaker")
    message: str = Field(..., description="Summary message")


# List responses
class SpeakerListResponse(BaseModel):
    """Response for listing all speakers."""
    speakers: List[SpeakerInfo] = Field(..., description="List of discovered speakers")
    count: int = Field(..., ge=0, description="Number of speakers discovered")
