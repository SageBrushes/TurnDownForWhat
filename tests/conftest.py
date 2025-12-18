"""Pytest configuration and shared fixtures for all tests."""
import os
import sys
import pytest
from pathlib import Path
from typing import Generator
import tempfile
from unittest.mock import Mock, PropertyMock

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


@pytest.fixture(autouse=True)
async def clear_sonos_cache():
    """Automatically clear Sonos service cache before each test."""
    # Clear before test
    try:
        from app.services import sonos_service
        await sonos_service.clear_speaker_cache()
    except:
        pass

    yield

    # Clear after test
    try:
        from app.services import sonos_service
        await sonos_service.clear_speaker_cache()
    except:
        pass


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


# Sonos Service Mock Fixtures
@pytest.fixture
def mock_speaker():
    """Create a mock SoCo speaker object with full properties."""
    speaker = Mock()
    speaker.ip_address = "192.168.1.100"
    speaker.player_name = "Living Room"
    speaker.volume = 50
    speaker.is_coordinator = True

    # Mock transport info
    speaker.get_current_transport_info.return_value = {
        "current_transport_state": "PLAYING"
    }

    # Mock track info
    speaker.get_current_track_info.return_value = {
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
    }

    # Mock control methods
    speaker.play = Mock()
    speaker.pause = Mock()
    speaker.stop = Mock()
    speaker.play_uri = Mock()
    speaker.clear_queue = Mock()

    return speaker


@pytest.fixture
def mock_multiple_speakers():
    """Create a list of mock SoCo speaker objects."""
    speakers = []

    speaker_data = [
        ("192.168.1.100", "Living Room", 50, True),
        ("192.168.1.101", "Bedroom", 30, True),
        ("192.168.1.102", "Kitchen", 40, True),
    ]

    for ip, name, volume, is_coord in speaker_data:
        speaker = Mock()
        speaker.ip_address = ip
        speaker.player_name = name
        speaker.volume = volume
        speaker.is_coordinator = is_coord

        speaker.get_current_transport_info = Mock(return_value={
            "current_transport_state": "PLAYING"
        })
        speaker.get_current_track_info = Mock(return_value={
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
        })

        speakers.append(speaker)

    return speakers


# FastAPI App Fixtures
@pytest.fixture
def app(mock_env_vars):
    """Create FastAPI app instance for testing."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def app_client(app, mock_env_vars):
    """Create TestClient for making API requests."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def test_client(app_client):
    """Alias for app_client for backward compatibility with existing tests."""
    return app_client


@pytest.fixture
def connection_manager():
    """Get ConnectionManager instance for testing."""
    from app.services.websocket_manager import ConnectionManager
    manager = ConnectionManager()
    # Clear any existing connections before test
    manager.active_connections.clear()
    yield manager
    # Clear connections after test
    manager.active_connections.clear()


@pytest.fixture
def mock_settings(mock_env_vars):
    """Get Settings instance with mocked environment variables."""
    from app.config import Settings
    return Settings()
