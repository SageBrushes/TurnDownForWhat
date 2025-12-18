"""Pytest configuration and shared fixtures for all tests."""
import os
import pytest
from pathlib import Path
from typing import Generator
import tempfile


@pytest.fixture(autouse=True)
def clean_env():
    """Automatically clean environment variables before each test."""
    # Save original env vars
    original_env = os.environ.copy()

    # Yield control to test
    yield

    # Restore original environment after test
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_audio_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


@pytest.fixture
def mock_env_vars(monkeypatch) -> dict:
    """Set up mock environment variables for testing."""
    env_vars = {
        "ELEVENLABS_API_KEY": "test_api_key_12345",
        "HOST": "127.0.0.1",
        "PORT": "8000",
        "API_KEY": "test_secret_key",
        "AUDIO_DIR": "static/audio",
        "SPEAKER_DISCOVERY_INTERVAL_MINUTES": "5",
        "AUDIO_CLEANUP_MAX_AGE_MINUTES": "60",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def minimal_env_vars(monkeypatch) -> dict:
    """Set up minimal required environment variables."""
    env_vars = {
        "ELEVENLABS_API_KEY": "test_api_key_12345",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def temp_env_file(tmp_path: Path) -> Path:
    """Create a temporary .env file for testing."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ELEVENLABS_API_KEY=test_key_from_file\n"
        "HOST=192.168.1.100\n"
        "PORT=9000\n"
    )
    return env_file


@pytest.fixture
def mock_speaker_data() -> dict:
    """Mock data for a Sonos speaker."""
    return {
        "ip": "192.168.1.100",
        "name": "Living Room",
        "volume": 50,
        "is_playing": True,
        "current_track": "Test Track",
    }


@pytest.fixture
def mock_multiple_speakers() -> list:
    """Mock data for multiple Sonos speakers."""
    return [
        {
            "ip": "192.168.1.100",
            "name": "Living Room",
            "volume": 50,
            "is_playing": True,
        },
        {
            "ip": "192.168.1.101",
            "name": "Bedroom",
            "volume": 30,
            "is_playing": False,
        },
        {
            "ip": "192.168.1.102",
            "name": "Kitchen",
            "volume": 40,
            "is_playing": True,
        },
    ]


@pytest.fixture
def sample_tts_text() -> str:
    """Sample text for TTS generation tests."""
    return "Hello, this is a test message for the Sonos TTS service."


@pytest.fixture
def sample_audio_file(temp_audio_dir: Path) -> Path:
    """Create a sample audio file for testing."""
    audio_file = temp_audio_dir / "test_audio.mp3"
    # Create a minimal valid file
    audio_file.write_bytes(b"fake audio content")
    return audio_file


# Async test configuration
@pytest.fixture
def event_loop_policy():
    """Set event loop policy for async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# Mark async tests automatically
def pytest_collection_modifyitems(items):
    """Automatically mark async tests."""
    for item in items:
        if "asyncio" in item.keywords:
            item.add_marker(pytest.mark.asyncio)
