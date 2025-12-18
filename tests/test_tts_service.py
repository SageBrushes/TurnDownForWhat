"""
Tests for TTS Service (ElevenLabs integration)

Following TDD approach - these tests are written BEFORE implementation.
"""

import pytest
import os
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List

# Note: These imports will fail until we implement the service
# This is expected in TDD - we write tests first!
try:
    from app.services.tts_service import (
        generate_tts_audio,
        get_available_voices,
        get_audio_url,
        Voice,
        TTSError,
        RateLimitError,
        InvalidAPIKeyError,
    )
except ImportError:
    # Allow tests to be collected even before implementation
    pass


# Fixtures
@pytest.fixture
def mock_elevenlabs_client():
    """Mock ElevenLabs client for testing."""
    with patch("app.services.tts_service.ElevenLabs") as mock_client:
        yield mock_client


@pytest.fixture
def audio_dir(tmp_path):
    """Create a temporary audio directory for testing."""
    audio_path = tmp_path / "audio"
    audio_path.mkdir()
    return audio_path


@pytest.fixture
def mock_audio_bytes():
    """Mock MP3 audio data."""
    return b"MOCK_MP3_DATA_" + b"\x00" * 1000


@pytest.fixture
def sample_voices():
    """Sample voice data from ElevenLabs API."""
    return [
        {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",
            "name": "Rachel",
            "category": "premade",
            "labels": {"accent": "american", "description": "calm", "age": "young"},
        },
        {
            "voice_id": "AZnzlk1XvdvUeBnXmlld",
            "name": "Domi",
            "category": "premade",
            "labels": {"accent": "american", "description": "strong", "age": "young"},
        },
    ]


# Test: generate_tts_audio
@pytest.mark.asyncio
async def test_generate_tts_creates_file(
    tmp_path, mock_elevenlabs_client, mock_audio_bytes
):
    """
    Test that generate_tts_audio creates an MP3 file.

    RED phase: This will fail until we implement the function.
    """
    # Mock the ElevenLabs API response
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance

    # Mock the generate method to return audio bytes
    mock_client_instance.generate.return_value = iter([mock_audio_bytes])

    # Configure the audio directory
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        # When: Generate TTS
        filename = await generate_tts_audio(
            text="Hello, this is a test",
            voice="Rachel",
            api_key="test_api_key_123"
        )

        # Then: File should exist
        assert filename is not None
        assert filename.endswith(".mp3")

        file_path = audio_dir / filename
        assert file_path.exists()
        assert file_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_generate_tts_uses_unique_filenames(
    tmp_path, mock_elevenlabs_client, mock_audio_bytes
):
    """
    Test that each TTS generation creates a unique filename.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.return_value = iter([mock_audio_bytes])

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        # Generate two TTS files
        filename1 = await generate_tts_audio(
            text="First message",
            voice="Rachel",
            api_key="test_key"
        )
        filename2 = await generate_tts_audio(
            text="Second message",
            voice="Rachel",
            api_key="test_key"
        )

        # Filenames should be different
        assert filename1 != filename2

        # Both files should exist
        assert (audio_dir / filename1).exists()
        assert (audio_dir / filename2).exists()


@pytest.mark.asyncio
async def test_generate_tts_with_invalid_api_key(mock_elevenlabs_client):
    """
    Test that invalid API key raises InvalidAPIKeyError.

    Critical test case from requirements.
    """
    # Mock API error for invalid key
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.side_effect = Exception("Invalid API key")

    with pytest.raises(InvalidAPIKeyError) as exc_info:
        await generate_tts_audio(
            text="Test",
            voice="Rachel",
            api_key="invalid_key"
        )

    assert "api key" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_tts_with_missing_api_key():
    """
    Test that missing API key raises InvalidAPIKeyError.
    """
    with pytest.raises(InvalidAPIKeyError):
        await generate_tts_audio(
            text="Test",
            voice="Rachel",
            api_key=""
        )


@pytest.mark.asyncio
async def test_generate_tts_rate_limit_error(mock_elevenlabs_client):
    """
    Test that rate limit errors are properly handled.

    Critical test case from requirements.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance

    # Mock rate limit error
    rate_limit_error = Exception("Rate limit exceeded")
    mock_client_instance.generate.side_effect = rate_limit_error

    with pytest.raises(RateLimitError) as exc_info:
        await generate_tts_audio(
            text="Test",
            voice="Rachel",
            api_key="valid_key"
        )

    assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_tts_api_failure(mock_elevenlabs_client):
    """
    Test generic API failures are wrapped in TTSError.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.side_effect = Exception("Network error")

    with pytest.raises(TTSError) as exc_info:
        await generate_tts_audio(
            text="Test",
            voice="Rachel",
            api_key="valid_key"
        )

    assert "Network error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_tts_empty_text():
    """
    Test that empty text is rejected.
    """
    with pytest.raises(ValueError) as exc_info:
        await generate_tts_audio(
            text="",
            voice="Rachel",
            api_key="valid_key"
        )

    assert "text" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_tts_text_too_long():
    """
    Test that excessively long text is rejected (ElevenLabs has limits).
    """
    long_text = "A" * 10000  # Way too long

    with pytest.raises(ValueError) as exc_info:
        await generate_tts_audio(
            text=long_text,
            voice="Rachel",
            api_key="valid_key"
        )

    assert "long" in str(exc_info.value).lower() or "length" in str(exc_info.value).lower()


# Test: get_available_voices
@pytest.mark.asyncio
async def test_get_available_voices_returns_list(
    mock_elevenlabs_client, sample_voices
):
    """
    Test that get_available_voices returns a list of Voice objects.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance

    # Mock the voices.get_all() method
    mock_voices = Mock()
    mock_client_instance.voices = mock_voices

    # Create mock voice objects
    mock_voice_objects = []
    for v in sample_voices:
        mock_voice = Mock()
        mock_voice.voice_id = v["voice_id"]
        mock_voice.name = v["name"]
        mock_voice.category = v["category"]
        mock_voice.labels = v["labels"]
        mock_voice_objects.append(mock_voice)

    mock_voices.get_all.return_value = Mock(voices=mock_voice_objects)

    # When: Get available voices
    voices = await get_available_voices(api_key="test_key")

    # Then: Should return list of Voice objects
    assert isinstance(voices, list)
    assert len(voices) == 2
    assert all(isinstance(v, Voice) for v in voices)

    # Verify voice data
    assert voices[0].name == "Rachel"
    assert voices[1].name == "Domi"


@pytest.mark.asyncio
async def test_get_available_voices_with_invalid_key(mock_elevenlabs_client):
    """
    Test that invalid API key is handled when fetching voices.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.voices.get_all.side_effect = Exception("Invalid API key")

    with pytest.raises(InvalidAPIKeyError):
        await get_available_voices(api_key="invalid_key")


@pytest.mark.asyncio
async def test_get_available_voices_empty_list(mock_elevenlabs_client):
    """
    Test handling when no voices are available.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.voices.get_all.return_value = Mock(voices=[])

    voices = await get_available_voices(api_key="test_key")

    assert isinstance(voices, list)
    assert len(voices) == 0


# Test: get_audio_url
def test_get_audio_url_builds_correct_url():
    """
    Test that get_audio_url builds the correct URL format.

    Sonos needs complete file URLs for playback.
    """
    filename = "test_audio_12345.mp3"
    local_ip = "192.168.1.100"
    port = 8000

    url = get_audio_url(filename, local_ip, port)

    # Should return a complete HTTP URL
    assert url.startswith("http://")
    assert local_ip in url
    assert str(port) in url
    assert filename in url
    assert url.endswith(".mp3")

    # Expected format: http://192.168.1.100:8000/static/audio/test_audio_12345.mp3
    expected = f"http://{local_ip}:{port}/static/audio/{filename}"
    assert url == expected


def test_get_audio_url_with_default_port():
    """
    Test URL generation with default port.
    """
    filename = "test.mp3"
    local_ip = "10.0.0.5"

    url = get_audio_url(filename, local_ip)

    assert "10.0.0.5" in url
    assert "test.mp3" in url


def test_get_audio_url_validates_filename():
    """
    Test that invalid filenames are rejected.
    """
    with pytest.raises(ValueError):
        get_audio_url("", "192.168.1.1")

    with pytest.raises(ValueError):
        get_audio_url("../../../etc/passwd", "192.168.1.1")


def test_get_audio_url_validates_ip():
    """
    Test that invalid IP addresses are rejected.
    """
    with pytest.raises(ValueError):
        get_audio_url("test.mp3", "")

    with pytest.raises(ValueError):
        get_audio_url("test.mp3", "not-an-ip")


# Test: Voice model
def test_voice_model_creation():
    """
    Test that Voice model can be created with proper fields.
    """
    voice = Voice(
        voice_id="test_id_123",
        name="Test Voice",
        category="premade",
        labels={"accent": "british"}
    )

    assert voice.voice_id == "test_id_123"
    assert voice.name == "Test Voice"
    assert voice.category == "premade"
    assert voice.labels["accent"] == "british"


def test_voice_model_serialization():
    """
    Test that Voice can be serialized to dict (for API responses).
    """
    voice = Voice(
        voice_id="abc123",
        name="Alice",
        category="premade",
        labels={}
    )

    voice_dict = voice.model_dump() if hasattr(voice, 'model_dump') else voice.dict()

    assert isinstance(voice_dict, dict)
    assert voice_dict["voice_id"] == "abc123"
    assert voice_dict["name"] == "Alice"


# Edge Cases
@pytest.mark.asyncio
async def test_generate_tts_with_special_characters(
    tmp_path, mock_elevenlabs_client, mock_audio_bytes
):
    """
    Test TTS generation with special characters and Unicode.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.return_value = iter([mock_audio_bytes])

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        text_with_special_chars = "Hello! How are you? 😊 Testing 123... #python"

        filename = await generate_tts_audio(
            text=text_with_special_chars,
            voice="Rachel",
            api_key="test_key"
        )

        assert filename is not None
        assert (audio_dir / filename).exists()


@pytest.mark.asyncio
async def test_generate_tts_concurrent_requests(
    tmp_path, mock_elevenlabs_client, mock_audio_bytes
):
    """
    Test that concurrent TTS generations work correctly.
    """
    import asyncio

    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.return_value = iter([mock_audio_bytes])

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        # Generate 5 TTS files concurrently
        tasks = [
            generate_tts_audio(f"Message {i}", "Rachel", "test_key")
            for i in range(5)
        ]

        filenames = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(filenames) == 5
        assert len(set(filenames)) == 5  # All unique

        # All files should exist
        for filename in filenames:
            assert (audio_dir / filename).exists()


@pytest.mark.asyncio
async def test_generate_tts_preserves_audio_quality(
    tmp_path, mock_elevenlabs_client
):
    """
    Test that generated audio bytes are written correctly (no corruption).
    """
    # Create realistic mock MP3 data
    mock_mp3_data = b"ID3\x04\x00\x00" + b"\x00" * 1000  # MP3 header + data

    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.return_value = iter([mock_mp3_data])

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        filename = await generate_tts_audio(
            text="Test audio quality",
            voice="Rachel",
            api_key="test_key"
        )

        # Read back the file
        file_path = audio_dir / filename
        with open(file_path, "rb") as f:
            saved_data = f.read()

        # Should match exactly what the API returned
        assert saved_data == mock_mp3_data


# Performance tests
@pytest.mark.asyncio
@pytest.mark.slow
async def test_generate_tts_handles_large_text(
    tmp_path, mock_elevenlabs_client, mock_audio_bytes
):
    """
    Test that reasonably large text (within limits) is handled.
    """
    mock_client_instance = Mock()
    mock_elevenlabs_client.return_value = mock_client_instance
    mock_client_instance.generate.return_value = iter([mock_audio_bytes])

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    # Create text at the upper limit (e.g., 5000 chars)
    large_text = "A" * 5000

    with patch("app.services.tts_service.AUDIO_DIR", audio_dir):
        filename = await generate_tts_audio(
            text=large_text,
            voice="Rachel",
            api_key="test_key"
        )

        assert filename is not None
        assert (audio_dir / filename).exists()
