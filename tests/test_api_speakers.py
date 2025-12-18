"""Comprehensive tests for Speaker API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.speakers import router
from app.utils.errors import ErrorCode


# Create a test app with the router
@pytest.fixture
def app():
    """Create a FastAPI test app."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_speakers_data():
    """Mock speaker discovery data."""
    return [
        {"ip": "192.168.1.100", "name": "Living Room", "volume": 50, "is_coordinator": True},
        {"ip": "192.168.1.101", "name": "Bedroom", "volume": 30, "is_coordinator": True},
        {"ip": "192.168.1.102", "name": "Kitchen", "volume": 40, "is_coordinator": False},
    ]


@pytest.fixture
def mock_speaker_status():
    """Mock detailed speaker status."""
    return {
        "ip": "192.168.1.100",
        "name": "Living Room",
        "volume": 50,
        "transport_state": "PLAYING",
        "is_playing": True,
        "is_paused": False,
        "is_stopped": False,
        "current_track": {
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album"
        }
    }


class TestListSpeakers:
    """Test GET /api/speakers endpoint."""

    def test_list_speakers_success(self, client, mock_speakers_data):
        """Test successful speaker listing."""
        with patch("app.api.speakers.sonos_service.discover_speakers", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = mock_speakers_data

            response = client.get("/api/speakers")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            assert data[0]["ip"] == "192.168.1.100"
            assert data[0]["name"] == "Living Room"
            assert data[0]["volume"] == 50

    def test_list_speakers_empty(self, client):
        """Test speaker listing when no speakers found."""
        with patch("app.api.speakers.sonos_service.discover_speakers", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []

            response = client.get("/api/speakers")

            assert response.status_code == 200
            assert response.json() == []

    def test_list_speakers_discovery_error(self, client):
        """Test speaker listing when discovery fails."""
        with patch("app.api.speakers.sonos_service.discover_speakers", new_callable=AsyncMock) as mock_discover:
            mock_discover.side_effect = Exception("Network error")

            response = client.get("/api/speakers")

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "error_code" in data["detail"]


class TestGetSpeakerStatus:
    """Test GET /api/speakers/{ip}/status endpoint."""

    def test_get_speaker_status_success(self, client, mock_speaker_status):
        """Test successful status retrieval."""
        with patch("app.api.speakers.sonos_service.get_speaker_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_speaker_status

            response = client.get("/api/speakers/192.168.1.100/status")

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert data["name"] == "Living Room"
            assert data["is_playing"] is True
            assert data["current_track"]["title"] == "Test Track"

    def test_get_speaker_status_unreachable(self, client):
        """Test status retrieval for unreachable speaker."""
        from fastapi import HTTPException
        from app.utils.errors import speaker_unreachable_error

        with patch("app.api.speakers.sonos_service.get_speaker_status", new_callable=AsyncMock) as mock_status:
            mock_status.side_effect = speaker_unreachable_error("192.168.1.200")

            response = client.get("/api/speakers/192.168.1.200/status")

            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["error_code"] == ErrorCode.SPEAKER_UNREACHABLE.value


class TestSetSpeakerVolume:
    """Test POST /api/speakers/{ip}/volume endpoint."""

    def test_set_volume_success(self, client):
        """Test successful volume setting."""
        with patch("app.api.speakers.sonos_service.set_speaker_volume", new_callable=AsyncMock) as mock_set:
            mock_set.return_value = {"ip": "192.168.1.100", "volume": 75, "message": "Volume set to 75"}

            response = client.post("/api/speakers/192.168.1.100/volume", json={"volume": 75})

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert data["volume"] == 75
            mock_set.assert_called_once_with("192.168.1.100", 75)

    def test_set_volume_invalid_too_high(self, client):
        """Test setting volume above 100."""
        response = client.post("/api/speakers/192.168.1.100/volume", json={"volume": 101})

        assert response.status_code == 422  # Pydantic validation error

    def test_set_volume_invalid_too_low(self, client):
        """Test setting volume below 0."""
        response = client.post("/api/speakers/192.168.1.100/volume", json={"volume": -1})

        assert response.status_code == 422  # Pydantic validation error

    def test_set_volume_missing_parameter(self, client):
        """Test volume request without volume parameter."""
        response = client.post("/api/speakers/192.168.1.100/volume", json={})

        assert response.status_code == 422  # Missing required field

    def test_set_volume_speaker_unreachable(self, client):
        """Test volume setting for unreachable speaker."""
        from app.utils.errors import speaker_unreachable_error

        with patch("app.api.speakers.sonos_service.set_speaker_volume", new_callable=AsyncMock) as mock_set:
            mock_set.side_effect = speaker_unreachable_error("192.168.1.100")

            response = client.post("/api/speakers/192.168.1.100/volume", json={"volume": 50})

            assert response.status_code == 503
            assert response.json()["detail"]["error_code"] == ErrorCode.SPEAKER_UNREACHABLE.value


class TestFadeSpeakerVolume:
    """Test POST /api/speakers/{ip}/fade endpoint."""

    def test_fade_volume_success(self, client):
        """Test successful volume fade."""
        with patch("app.api.speakers.sonos_service.fade_speaker_volume", new_callable=AsyncMock) as mock_fade:
            mock_fade.return_value = {
                "ip": "192.168.1.100",
                "volume": 80,
                "direction": "up",
                "steps": 100,
                "duration": 5.2,
                "message": "Faded volume up to 80 in 100 steps"
            }

            response = client.post("/api/speakers/192.168.1.100/fade", json={"target_volume": 80})

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert data["volume"] == 80
            assert data["direction"] == "up"
            assert data["steps"] == 100

    def test_fade_volume_invalid(self, client):
        """Test fade with invalid volume."""
        response = client.post("/api/speakers/192.168.1.100/fade", json={"target_volume": 150})

        assert response.status_code == 422  # Pydantic validation error

    def test_fade_concurrent_operation(self, client):
        """Test fade when another fade is already in progress."""
        from app.utils.errors import concurrent_operation_error

        with patch("app.api.speakers.sonos_service.fade_speaker_volume", new_callable=AsyncMock) as mock_fade:
            mock_fade.side_effect = concurrent_operation_error("speaker 192.168.1.100")

            response = client.post("/api/speakers/192.168.1.100/fade", json={"target_volume": 50})

            assert response.status_code == 409
            assert response.json()["detail"]["error_code"] == ErrorCode.CONCURRENT_OPERATION.value

    def test_fade_with_websocket_broadcast(self, client):
        """Test that fade broadcasts progress via WebSocket."""
        with patch("app.api.speakers.sonos_service.fade_speaker_volume", new_callable=AsyncMock) as mock_fade:
            with patch("app.api.speakers.get_connection_manager") as mock_manager:
                mock_fade.return_value = {
                    "ip": "192.168.1.100",
                    "volume": 80,
                    "direction": "up",
                    "steps": 100,
                    "message": "Faded"
                }
                mock_conn_manager = Mock()
                mock_manager.return_value = mock_conn_manager

                response = client.post("/api/speakers/192.168.1.100/fade", json={"target_volume": 80})

                assert response.status_code == 200
                # Verify fade was called (callback is passed to it)
                assert mock_fade.called


class TestPlaySpeaker:
    """Test POST /api/speakers/{ip}/play endpoint."""

    def test_play_speaker_success(self, client):
        """Test successful play/resume."""
        with patch("app.api.speakers.sonos_service.play_speaker", new_callable=AsyncMock) as mock_play:
            mock_play.return_value = {"ip": "192.168.1.100", "message": "Playback resumed"}

            response = client.post("/api/speakers/192.168.1.100/play")

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert "resumed" in data["message"].lower()

    def test_play_speaker_unreachable(self, client):
        """Test play on unreachable speaker."""
        from app.utils.errors import speaker_unreachable_error

        with patch("app.api.speakers.sonos_service.play_speaker", new_callable=AsyncMock) as mock_play:
            mock_play.side_effect = speaker_unreachable_error("192.168.1.100")

            response = client.post("/api/speakers/192.168.1.100/play")

            assert response.status_code == 503


class TestPauseSpeaker:
    """Test POST /api/speakers/{ip}/pause endpoint."""

    def test_pause_speaker_success(self, client):
        """Test successful pause."""
        with patch("app.api.speakers.sonos_service.pause_speaker", new_callable=AsyncMock) as mock_pause:
            mock_pause.return_value = {"ip": "192.168.1.100", "message": "Playback paused"}

            response = client.post("/api/speakers/192.168.1.100/pause")

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert "paused" in data["message"].lower()

    def test_pause_speaker_unreachable(self, client):
        """Test pause on unreachable speaker."""
        from app.utils.errors import speaker_unreachable_error

        with patch("app.api.speakers.sonos_service.pause_speaker", new_callable=AsyncMock) as mock_pause:
            mock_pause.side_effect = speaker_unreachable_error("192.168.1.100")

            response = client.post("/api/speakers/192.168.1.100/pause")

            assert response.status_code == 503


class TestStopSpeaker:
    """Test POST /api/speakers/{ip}/stop endpoint."""

    def test_stop_speaker_success(self, client):
        """Test successful stop."""
        with patch("app.api.speakers.sonos_service.stop_speaker", new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = {"ip": "192.168.1.100", "message": "Playback stopped"}

            response = client.post("/api/speakers/192.168.1.100/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["ip"] == "192.168.1.100"
            assert "stopped" in data["message"].lower()

    def test_stop_speaker_unreachable(self, client):
        """Test stop on unreachable speaker."""
        from app.utils.errors import speaker_unreachable_error

        with patch("app.api.speakers.sonos_service.stop_speaker", new_callable=AsyncMock) as mock_stop:
            mock_stop.side_effect = speaker_unreachable_error("192.168.1.100")

            response = client.post("/api/speakers/192.168.1.100/stop")

            assert response.status_code == 503


class TestSetAllSpeakersVolume:
    """Test POST /api/speakers/volume/all endpoint."""

    def test_set_all_volumes_success(self, client):
        """Test setting volume on all speakers."""
        with patch("app.api.speakers.sonos_service.set_all_speakers_volume", new_callable=AsyncMock) as mock_set_all:
            mock_set_all.return_value = {
                "success_count": 3,
                "failed_count": 0,
                "results": [
                    {"ip": "192.168.1.100", "volume": 60, "message": "Volume set to 60"},
                    {"ip": "192.168.1.101", "volume": 60, "message": "Volume set to 60"},
                    {"ip": "192.168.1.102", "volume": 60, "message": "Volume set to 60"},
                ],
                "message": "Set volume to 60 on 3/3 speakers"
            }

            response = client.post("/api/speakers/volume/all", json={"volume": 60})

            assert response.status_code == 200
            data = response.json()
            assert data["success_count"] == 3
            assert data["failed_count"] == 0
            assert len(data["results"]) == 3

    def test_set_all_volumes_partial_failure(self, client):
        """Test setting volume when some speakers fail."""
        with patch("app.api.speakers.sonos_service.set_all_speakers_volume", new_callable=AsyncMock) as mock_set_all:
            mock_set_all.return_value = {
                "success_count": 2,
                "failed_count": 1,
                "results": [
                    {"ip": "192.168.1.100", "volume": 60, "message": "Volume set to 60"},
                    {"ip": "192.168.1.101", "volume": 60, "message": "Volume set to 60"},
                    {"error": "Connection timeout"},
                ],
                "message": "Set volume to 60 on 2/3 speakers"
            }

            response = client.post("/api/speakers/volume/all", json={"volume": 60})

            assert response.status_code == 200
            data = response.json()
            assert data["success_count"] == 2
            assert data["failed_count"] == 1

    def test_set_all_volumes_invalid(self, client):
        """Test set all with invalid volume."""
        response = client.post("/api/speakers/volume/all", json={"volume": 150})

        assert response.status_code == 422  # Pydantic validation error


class TestWebSocketIntegration:
    """Test WebSocket broadcast integration."""

    def test_volume_change_broadcasts_update(self, client):
        """Test that volume changes broadcast speaker updates."""
        with patch("app.api.speakers.sonos_service.set_speaker_volume", new_callable=AsyncMock) as mock_set:
            with patch("app.api.speakers.get_connection_manager") as mock_manager:
                mock_set.return_value = {"ip": "192.168.1.100", "volume": 75, "message": "Volume set"}
                mock_conn_manager = Mock()
                mock_conn_manager.broadcast = AsyncMock()
                mock_manager.return_value = mock_conn_manager

                response = client.post("/api/speakers/192.168.1.100/volume", json={"volume": 75})

                assert response.status_code == 200
                # Verify broadcast was called
                assert mock_conn_manager.broadcast.called


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_generic_error_handling(self, client):
        """Test that unexpected errors return 500."""
        with patch("app.api.speakers.sonos_service.discover_speakers", new_callable=AsyncMock) as mock_discover:
            mock_discover.side_effect = Exception("Unexpected error")

            response = client.get("/api/speakers")

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "error_code" in data["detail"]

    def test_http_exception_propagation(self, client):
        """Test that HTTPExceptions are properly propagated."""
        from fastapi import HTTPException
        from app.utils.errors import error_response, ErrorCode

        with patch("app.api.speakers.sonos_service.get_speaker_status", new_callable=AsyncMock) as mock_status:
            mock_status.side_effect = HTTPException(
                status_code=503,
                detail=error_response("Test error", ErrorCode.SPEAKER_UNREACHABLE)
            )

            response = client.get("/api/speakers/192.168.1.100/status")

            assert response.status_code == 503
