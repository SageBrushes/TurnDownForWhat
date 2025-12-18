"""Application configuration using Pydantic BaseSettings."""
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required settings
    ELEVENLABS_API_KEY: str = Field(..., description="ElevenLabs API key for TTS generation")

    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Host to bind the server to")
    PORT: int = Field(default=8000, description="Port to bind the server to", ge=1, le=65535)

    # Optional API authentication
    API_KEY: Optional[str] = Field(default=None, description="Optional API key for authentication")

    # Audio file settings
    AUDIO_DIR: Path = Field(default=Path("static/audio"), description="Directory for generated audio files")

    # Background task intervals (in minutes)
    SPEAKER_DISCOVERY_INTERVAL_MINUTES: int = Field(
        default=5,
        description="How often to refresh speaker discovery cache",
        ge=1,
        le=30
    )
    AUDIO_CLEANUP_MAX_AGE_MINUTES: int = Field(
        default=60,
        description="Delete audio files older than this many minutes",
        ge=1
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("AUDIO_DIR", mode="before")
    @classmethod
    def convert_audio_dir_to_path(cls, v):
        """Convert AUDIO_DIR to Path object."""
        if isinstance(v, str):
            return Path(v)
        return v


# Global settings instance
settings = Settings()
