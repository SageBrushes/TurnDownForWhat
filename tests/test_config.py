"""Tests for app configuration."""
import os
from pathlib import Path
import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(monkeypatch, tmp_path):
    """Test that Settings loads environment variables correctly."""
    # Given: Environment variables are set
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test_api_key_123")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_KEY", "my_secret_key")
    monkeypatch.setenv("AUDIO_DIR", str(tmp_path / "audio"))

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Values should match environment
    assert settings.ELEVENLABS_API_KEY == "test_api_key_123"
    assert settings.HOST == "127.0.0.1"
    assert settings.PORT == 8080
    assert settings.API_KEY == "my_secret_key"
    assert settings.AUDIO_DIR == tmp_path / "audio"


def test_settings_has_default_values(monkeypatch):
    """Test that Settings has sensible defaults."""
    # Given: Required env vars are set, others are not
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Should have default values
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000
    assert settings.API_KEY is None
    assert settings.AUDIO_DIR == Path("static/audio")


def test_settings_requires_elevenlabs_api_key(monkeypatch):
    """Test that ELEVENLABS_API_KEY is required."""
    # Given: ELEVENLABS_API_KEY is not set
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    # When: Settings is instantiated
    # Then: Should raise ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "ELEVENLABS_API_KEY" in str(exc_info.value)


def test_settings_validates_port_range(monkeypatch):
    """Test that PORT must be in valid range."""
    # Given: Invalid port number
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
    monkeypatch.setenv("PORT", "99999")  # Too high

    # When: Settings is instantiated
    # Then: Should raise ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "PORT" in str(exc_info.value) or "port" in str(exc_info.value).lower()


def test_settings_loads_from_env_file(tmp_path, monkeypatch):
    """Test that Settings can load from .env file."""
    # Given: .env file exists with values
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ELEVENLABS_API_KEY=file_api_key\n"
        "HOST=192.168.1.100\n"
        "PORT=9000\n"
    )

    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Should load values from file
    assert settings.ELEVENLABS_API_KEY == "file_api_key"
    assert settings.HOST == "192.168.1.100"
    assert settings.PORT == 9000


def test_settings_creates_audio_dir_path():
    """Test that AUDIO_DIR is properly converted to Path."""
    # Given: AUDIO_DIR as string in env
    import os
    os.environ["ELEVENLABS_API_KEY"] = "test_key"
    os.environ["AUDIO_DIR"] = "custom/audio/path"

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Should be a Path object
    assert isinstance(settings.AUDIO_DIR, Path)
    assert str(settings.AUDIO_DIR) == "custom/audio/path"

    # Cleanup
    del os.environ["AUDIO_DIR"]
    del os.environ["ELEVENLABS_API_KEY"]


def test_settings_speaker_discovery_interval():
    """Test that speaker discovery interval has reasonable default."""
    # Given: Required env vars
    import os
    os.environ["ELEVENLABS_API_KEY"] = "test_key"

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Should have discovery interval
    assert hasattr(settings, "SPEAKER_DISCOVERY_INTERVAL_MINUTES")
    assert settings.SPEAKER_DISCOVERY_INTERVAL_MINUTES > 0
    assert settings.SPEAKER_DISCOVERY_INTERVAL_MINUTES <= 30

    # Cleanup
    del os.environ["ELEVENLABS_API_KEY"]


def test_settings_cleanup_interval():
    """Test that audio cleanup interval has reasonable default."""
    # Given: Required env vars
    import os
    os.environ["ELEVENLABS_API_KEY"] = "test_key"

    # When: Settings is instantiated
    from app.config import Settings
    settings = Settings()

    # Then: Should have cleanup interval
    assert hasattr(settings, "AUDIO_CLEANUP_MAX_AGE_MINUTES")
    assert settings.AUDIO_CLEANUP_MAX_AGE_MINUTES > 0

    # Cleanup
    del os.environ["ELEVENLABS_API_KEY"]
