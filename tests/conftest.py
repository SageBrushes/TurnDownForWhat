"""Pytest configuration and shared fixtures for all tests."""
import os
import sys
import pytest
from pathlib import Path
from typing import Generator
import tempfile
from unittest.mock import Mock, PropertyMock
from httpx import AsyncClient

# Add app directory to Python path for imports
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


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


# Mock Sonos speaker fixtures for sonos_service tests
@pytest.fixture
def mock_speaker():
    """Create a mock Sonos speaker (SoCo object) with standard properties."""
    mock = Mock()
    mock.ip_address = "192.168.1.100"
    type(mock).player_name = PropertyMock(return_value="Living Room")
    type(mock).volume = PropertyMock(return_value=50)
    mock.is_coordinator = True

    # Mock transport info
    mock.get_current_transport_info.return_value = {
        "current_transport_state": "PLAYING"
    }

    # Mock track info
    mock.get_current_track_info.return_value = {
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": "0:03:45"
    }

    # Mock playback methods
    mock.play_uri = Mock()
    mock.clear_queue = Mock()
    mock.pause = Mock()
    mock.stop = Mock()

    return mock


@pytest.fixture
def mock_multiple_speakers():
    """Create multiple mock Sonos speakers for discovery tests."""
    speakers = []

    # Speaker 1
    speaker1 = Mock()
    speaker1.ip_address = "192.168.1.100"
    type(speaker1).player_name = PropertyMock(return_value="Living Room")
    type(speaker1).volume = PropertyMock(return_value=50)
    speaker1.is_coordinator = True
    speaker1.get_current_transport_info.return_value = {"current_transport_state": "PLAYING"}
    speaker1.get_current_track_info.return_value = {
        "title": "Track 1", "artist": "Artist 1", "album": "Album 1", "duration": "0:03:00"
    }
    speakers.append(speaker1)

    # Speaker 2
    speaker2 = Mock()
    speaker2.ip_address = "192.168.1.101"
    type(speaker2).player_name = PropertyMock(return_value="Bedroom")
    type(speaker2).volume = PropertyMock(return_value=30)
    speaker2.is_coordinator = True
    speaker2.get_current_transport_info.return_value = {"current_transport_state": "STOPPED"}
    speaker2.get_current_track_info.return_value = {"title": "", "artist": "", "album": "", "duration": ""}
    speakers.append(speaker2)

    # Speaker 3
    speaker3 = Mock()
    speaker3.ip_address = "192.168.1.102"
    type(speaker3).player_name = PropertyMock(return_value="Kitchen")
    type(speaker3).volume = PropertyMock(return_value=40)
    speaker3.is_coordinator = True
    speaker3.get_current_transport_info.return_value = {"current_transport_state": "PAUSED_PLAYBACK"}
    speaker3.get_current_track_info.return_value = {
        "title": "Track 3", "artist": "Artist 3", "album": "Album 3", "duration": "0:04:30"
    }
    speakers.append(speaker3)

    return speakers


# FastAPI test client fixture for API endpoint tests
@pytest.fixture
async def test_client(mock_env_vars):
    """Create a test client for FastAPI app."""
    # Import here to avoid circular dependencies and ensure env vars are set
    from fastapi import FastAPI
    from app.api import tts

    # Create a minimal FastAPI app for testing
    app = FastAPI()
    app.include_router(tts.router)

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_settings(mock_env_vars):
    """Create mock settings object for testing."""
    from app.config import Settings
    return Settings()
