"""Comprehensive tests for TTS API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi import HTTPException
from pathlib import Path

from app.models import TTSRequest, TTSPlaybackRequest
from app.services.tts_service import TTSError, InvalidAPIKeyError, RateLimitError


class TestGenerateTTSEndpoint:
    """Test POST /api/tts/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_tts_success(self, test_client, mock_settings):
        """Test successful TTS generation."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            # Mock TTS generation
            mock_tts_service.generate_tts_audio = AsyncMock(return_value="test123.mp3")
            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )

            # Mock Sonos playback
            mock_sonos_service.play_uri = AsyncMock(return_value={
                "ip": "192.168.1.100",
                "uri": "http://192.168.1.50:8000/static/audio/test123.mp3",
                "message": "Playing audio"
            })

            # Mock WebSocket manager
            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["audio_url"] == "http://192.168.1.50:8000/static/audio/test123.mp3"
            assert data["filename"] == "test123.mp3"
            assert data["text"] == "Hello world"
            assert data["voice"] == "Rachel"
            assert data["speaker_ips"] == ["192.168.1.100"]

            # Verify TTS service was called correctly
            mock_tts_service.generate_tts_audio.assert_called_once_with(
                text="Hello world",
                voice="Rachel",
                api_key=mock_settings.ELEVENLABS_API_KEY
            )

            # Verify Sonos service was called
            mock_sonos_service.play_uri.assert_called_once_with(
                "192.168.1.100",
                "http://192.168.1.50:8000/static/audio/test123.mp3"
            )

            # Verify WebSocket broadcast
            mock_ws.broadcast.assert_called_once()
            broadcast_call = mock_ws.broadcast.call_args[0][0]
            assert broadcast_call["type"] == "tts_started"

    @pytest.mark.asyncio
    async def test_generate_tts_multiple_speakers(self, test_client, mock_settings):
        """Test TTS generation with multiple speakers."""
        request_data = {
            "text": "Test message",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(return_value="test123.mp3")
            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )
            mock_sonos_service.play_uri = AsyncMock(return_value={"ip": "", "uri": "", "message": ""})

            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 200
            # Verify play_uri called for each speaker
            assert mock_sonos_service.play_uri.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_tts_empty_text(self, test_client):
        """Test TTS generation with empty text."""
        request_data = {
            "text": "",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_whitespace_only_text(self, test_client):
        """Test TTS generation with whitespace-only text."""
        request_data = {
            "text": "   ",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_text_too_long(self, test_client):
        """Test TTS generation with text exceeding maximum length."""
        request_data = {
            "text": "a" * 5001,  # Exceeds 5000 char limit
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_empty_voice(self, test_client):
        """Test TTS generation with empty voice."""
        request_data = {
            "text": "Hello world",
            "voice": "",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_no_speakers(self, test_client):
        """Test TTS generation with no speakers."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": []
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_missing_text(self, test_client):
        """Test TTS generation with missing text field."""
        request_data = {
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_missing_voice(self, test_client):
        """Test TTS generation with missing voice field."""
        request_data = {
            "text": "Hello world",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_missing_speaker_ips(self, test_client):
        """Test TTS generation with missing speaker_ips field."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel"
        }

        response = await test_client.post("/api/tts/generate", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_tts_invalid_api_key(self, test_client, mock_settings):
        """Test TTS generation with invalid API key."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(
                side_effect=InvalidAPIKeyError("Invalid API key")
            )

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 401
            data = response.json()
            assert "INVALID_API_KEY" in data["detail"]["error_code"]

    @pytest.mark.asyncio
    async def test_generate_tts_rate_limit_exceeded(self, test_client, mock_settings):
        """Test TTS generation when rate limit is exceeded."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded")
            )

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 429
            data = response.json()
            assert "RATE_LIMIT_EXCEEDED" in data["detail"]["error_code"]

    @pytest.mark.asyncio
    async def test_generate_tts_service_error(self, test_client, mock_settings):
        """Test TTS generation with general TTS service error."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(
                side_effect=TTSError("TTS generation failed")
            )

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 500
            data = response.json()
            assert "TTS_ERROR" in data["detail"]["error_code"]

    @pytest.mark.asyncio
    async def test_generate_tts_speaker_unreachable(self, test_client, mock_settings):
        """Test TTS generation when speaker is unreachable."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(return_value="test123.mp3")
            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )

            # Mock speaker failure
            mock_sonos_service.play_uri = AsyncMock(
                side_effect=HTTPException(status_code=503, detail={"error_code": "SPEAKER_UNREACHABLE"})
            )

            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_generate_tts_websocket_broadcast(self, test_client, mock_settings):
        """Test that WebSocket broadcast is sent on TTS generation."""
        request_data = {
            "text": "Hello world",
            "voice": "Rachel",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.generate_tts_audio = AsyncMock(return_value="test123.mp3")
            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )
            mock_sonos_service.play_uri = AsyncMock(return_value={"ip": "", "uri": "", "message": ""})

            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/generate", json=request_data)

            assert response.status_code == 200

            # Verify WebSocket broadcast was called
            mock_ws.broadcast.assert_called_once()
            broadcast_data = mock_ws.broadcast.call_args[0][0]
            assert broadcast_data["type"] == "tts_started"
            assert broadcast_data["data"]["text"] == "Hello world"
            assert broadcast_data["data"]["audio_url"] == "http://192.168.1.50:8000/static/audio/test123.mp3"


class TestGetVoicesEndpoint:
    """Test GET /api/tts/voices endpoint."""

    @pytest.mark.asyncio
    async def test_get_voices_success(self, test_client, mock_settings):
        """Test successful retrieval of available voices."""
        with patch("app.api.tts.tts_service") as mock_tts_service:
            # Create proper mock Voice objects with attributes
            voice1 = Mock()
            voice1.voice_id = "voice1"
            voice1.name = "Rachel"
            voice1.category = "premade"
            voice1.labels = {"accent": "american"}

            voice2 = Mock()
            voice2.voice_id = "voice2"
            voice2.name = "Domi"
            voice2.category = "premade"
            voice2.labels = {"accent": "american"}

            mock_voices = [voice1, voice2]

            mock_tts_service.get_available_voices = AsyncMock(return_value=mock_voices)

            response = await test_client.get("/api/tts/voices")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert len(data["voices"]) == 2
            assert data["voices"][0]["name"] == "Rachel"
            assert data["voices"][1]["name"] == "Domi"

            # Verify service was called with API key
            mock_tts_service.get_available_voices.assert_called_once_with(
                api_key=mock_settings.ELEVENLABS_API_KEY
            )

    @pytest.mark.asyncio
    async def test_get_voices_empty_list(self, test_client, mock_settings):
        """Test getting voices when none are available."""
        with patch("app.api.tts.tts_service") as mock_tts_service:
            mock_tts_service.get_available_voices = AsyncMock(return_value=[])

            response = await test_client.get("/api/tts/voices")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["voices"] == []

    @pytest.mark.asyncio
    async def test_get_voices_invalid_api_key(self, test_client, mock_settings):
        """Test getting voices with invalid API key."""
        with patch("app.api.tts.tts_service") as mock_tts_service:
            mock_tts_service.get_available_voices = AsyncMock(
                side_effect=InvalidAPIKeyError("Invalid API key")
            )

            response = await test_client.get("/api/tts/voices")

            assert response.status_code == 401
            data = response.json()
            assert "INVALID_API_KEY" in data["detail"]["error_code"]

    @pytest.mark.asyncio
    async def test_get_voices_service_error(self, test_client, mock_settings):
        """Test getting voices with service error."""
        with patch("app.api.tts.tts_service") as mock_tts_service:
            mock_tts_service.get_available_voices = AsyncMock(
                side_effect=TTSError("Failed to fetch voices")
            )

            response = await test_client.get("/api/tts/voices")

            assert response.status_code == 500
            data = response.json()
            assert "TTS_ERROR" in data["detail"]["error_code"]


class TestPlayExistingTTSEndpoint:
    """Test POST /api/tts/play endpoint."""

    @pytest.mark.asyncio
    async def test_play_existing_success(self, test_client, mock_settings, tmp_path):
        """Test successful playback of existing TTS audio."""
        # Create a temporary audio file
        audio_dir = tmp_path / "static" / "audio"
        audio_dir.mkdir(parents=True)
        audio_file = audio_dir / "test123.mp3"
        audio_file.write_bytes(b"fake audio data")

        request_data = {
            "filename": "test123.mp3",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.AUDIO_DIR", audio_dir), \
             patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )
            mock_sonos_service.play_uri = AsyncMock(return_value={
                "ip": "192.168.1.100",
                "uri": "http://192.168.1.50:8000/static/audio/test123.mp3",
                "message": "Playing audio"
            })

            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/play", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["filename"] == "test123.mp3"
            assert data["audio_url"] == "http://192.168.1.50:8000/static/audio/test123.mp3"
            assert data["speaker_ips"] == ["192.168.1.100"]

            # Verify play_uri was called
            mock_sonos_service.play_uri.assert_called_once()

    @pytest.mark.asyncio
    async def test_play_existing_file_not_found(self, test_client, tmp_path):
        """Test playback of non-existent file."""
        audio_dir = tmp_path / "static" / "audio"
        audio_dir.mkdir(parents=True)

        request_data = {
            "filename": "nonexistent.mp3",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.AUDIO_DIR", audio_dir):
            response = await test_client.post("/api/tts/play", json=request_data)

            assert response.status_code == 404
            data = response.json()
            assert "FILE_NOT_FOUND" in data["detail"]["error_code"]

    @pytest.mark.asyncio
    async def test_play_existing_invalid_filename(self, test_client):
        """Test playback with invalid filename (path traversal attempt)."""
        request_data = {
            "filename": "../../../etc/passwd",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/play", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_play_existing_non_mp3_file(self, test_client):
        """Test playback with non-MP3 file."""
        request_data = {
            "filename": "test.txt",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/play", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_play_existing_empty_filename(self, test_client):
        """Test playback with empty filename."""
        request_data = {
            "filename": "",
            "speaker_ips": ["192.168.1.100"]
        }

        response = await test_client.post("/api/tts/play", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_play_existing_no_speakers(self, test_client):
        """Test playback with no speakers."""
        request_data = {
            "filename": "test123.mp3",
            "speaker_ips": []
        }

        response = await test_client.post("/api/tts/play", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_play_existing_multiple_speakers(self, test_client, mock_settings, tmp_path):
        """Test playback on multiple speakers."""
        audio_dir = tmp_path / "static" / "audio"
        audio_dir.mkdir(parents=True)
        audio_file = audio_dir / "test123.mp3"
        audio_file.write_bytes(b"fake audio data")

        request_data = {
            "filename": "test123.mp3",
            "speaker_ips": ["192.168.1.100", "192.168.1.101"]
        }

        with patch("app.api.tts.AUDIO_DIR", audio_dir), \
             patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_connection_manager") as mock_ws_manager, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )
            mock_sonos_service.play_uri = AsyncMock(return_value={})

            mock_ws = AsyncMock()
            mock_ws_manager.return_value = mock_ws
            mock_ws.broadcast = AsyncMock()

            response = await test_client.post("/api/tts/play", json=request_data)

            assert response.status_code == 200
            # Verify play_uri called for each speaker
            assert mock_sonos_service.play_uri.call_count == 2

    @pytest.mark.asyncio
    async def test_play_existing_speaker_unreachable(self, test_client, mock_settings, tmp_path):
        """Test playback when speaker is unreachable."""
        audio_dir = tmp_path / "static" / "audio"
        audio_dir.mkdir(parents=True)
        audio_file = audio_dir / "test123.mp3"
        audio_file.write_bytes(b"fake audio data")

        request_data = {
            "filename": "test123.mp3",
            "speaker_ips": ["192.168.1.100"]
        }

        with patch("app.api.tts.AUDIO_DIR", audio_dir), \
             patch("app.api.tts.tts_service") as mock_tts_service, \
             patch("app.api.tts.sonos_service") as mock_sonos_service, \
             patch("app.api.tts.get_local_ip", return_value="192.168.1.50"):

            mock_tts_service.get_audio_url = Mock(
                return_value="http://192.168.1.50:8000/static/audio/test123.mp3"
            )
            mock_sonos_service.play_uri = AsyncMock(
                side_effect=HTTPException(status_code=503, detail={"error_code": "SPEAKER_UNREACHABLE"})
            )

            response = await test_client.post("/api/tts/play", json=request_data)

            assert response.status_code == 503
