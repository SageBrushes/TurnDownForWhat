"""Pytest configuration and shared fixtures for all tests."""
import os
import pytest
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, MagicMock
import asyncio


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
def mock_speaker():
    """Create a mock SoCo speaker object."""
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
    speaker.pause = Mock()
    speaker.stop = Mock()
    speaker.play_uri = Mock()
    speaker.clear_queue = Mock()

    return speaker


@pytest.fixture
def mock_multiple_speakers():
    """Create multiple mock SoCo speaker objects."""
    speakers = []
    ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
    names = ["Living Room", "Bedroom", "Kitchen"]
    volumes = [50, 30, 40]

    for ip, name, vol in zip(ips, names, volumes):
        speaker = Mock()
        speaker.ip_address = ip
        speaker.player_name = name
        speaker.volume = vol
        speaker.is_coordinator = True

        speaker.get_current_transport_info.return_value = {
            "current_transport_state": "PLAYING"
        }
        speaker.get_current_track_info.return_value = {
            "title": f"Track on {name}",
            "artist": "Test Artist",
            "album": "Test Album",
        }

        speaker.pause = Mock()
        speaker.stop = Mock()
        speaker.play_uri = Mock()
        speaker.clear_queue = Mock()

        speakers.append(speaker)

    return speakers


@pytest.fixture
def mock_unreachable_speaker():
    """Create a mock speaker that raises exceptions (simulates unreachable speaker)."""
    speaker = Mock()
    speaker.ip_address = "192.168.1.200"

    # All operations raise exceptions
    speaker.player_name = Mock(side_effect=Exception("Connection timeout"))
    speaker.volume = Mock(side_effect=Exception("Connection timeout"))
    speaker.get_current_transport_info = Mock(
        side_effect=Exception("Connection timeout")
    )
    speaker.get_current_track_info = Mock(side_effect=Exception("Connection timeout"))
    speaker.pause = Mock(side_effect=Exception("Connection timeout"))
    speaker.stop = Mock(side_effect=Exception("Connection timeout"))

    return speaker


@pytest.fixture(autouse=True)
def clear_speaker_cache_sync():
    """Clear speaker cache before each test."""
    # Import here to avoid circular imports
    from app.services import sonos_service
    import asyncio

    # Clear cache synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sonos_service.clear_speaker_cache())
    sonos_service._speaker_locks.clear()
    loop.close()

    yield

    # Clean up after test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sonos_service.clear_speaker_cache())
    sonos_service._speaker_locks.clear()
    loop.close()


# Async test configuration
@pytest.fixture
def event_loop_policy():
    """Set event loop policy for async tests."""
    return asyncio.DefaultEventLoopPolicy()


# Mark async tests automatically
def pytest_collection_modifyitems(items):
    """Automatically mark async tests."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
