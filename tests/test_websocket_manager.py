"""
Test suite for WebSocket Manager following TDD principles.

Tests cover:
- Connection management (connect/disconnect)
- Broadcasting to multiple clients
- Sending to individual clients
- Message serialization
- Error handling for disconnected clients
- Singleton pattern validation
"""

import pytest
from unittest.mock import AsyncMock
import json


# Mock WebSocket class for testing
class MockWebSocket:
    """Mock WebSocket for testing without actual connection"""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.sent_messages = []
        self.closed = False
        self.send_text = AsyncMock(side_effect=self._send_text)
        self.close = AsyncMock(side_effect=self._close)

    async def _send_text(self, data: str):
        """Track sent messages"""
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent_messages.append(data)

    async def _close(self):
        """Mark as closed"""
        self.closed = True

    def get_sent_messages(self):
        """Get all messages sent to this client"""
        return [json.loads(msg) for msg in self.sent_messages]


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection"""
    return MockWebSocket("test-client-1")


@pytest.fixture
def multiple_mock_websockets():
    """Create multiple mock WebSocket connections"""
    return [
        MockWebSocket("client-1"),
        MockWebSocket("client-2"),
        MockWebSocket("client-3"),
    ]


@pytest.fixture
async def connection_manager():
    """
    Create a fresh ConnectionManager instance for each test.
    Reset the singleton to avoid test interference.
    """
    # Import here to avoid circular dependencies
    from app.services.websocket_manager import ConnectionManager

    # Reset singleton
    ConnectionManager._instance = None
    manager = ConnectionManager()
    yield manager

    # Cleanup: disconnect all clients
    await manager.disconnect_all()


class TestConnectionManager:
    """Test ConnectionManager class"""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test that ConnectionManager follows singleton pattern"""
        from app.services.websocket_manager import ConnectionManager

        # Reset singleton
        ConnectionManager._instance = None

        # Create two instances
        manager1 = ConnectionManager()
        manager2 = ConnectionManager()

        # Should be the same instance
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_connect_adds_client(self, connection_manager, mock_websocket):
        """Test that connect() adds a client to active connections"""
        # Given: ConnectionManager with no clients
        assert len(connection_manager.active_connections) == 0

        # When: Connect a client
        await connection_manager.connect(mock_websocket)

        # Then: Client should be in active connections
        assert len(connection_manager.active_connections) == 1
        assert mock_websocket in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, connection_manager, mock_websocket):
        """Test that disconnect() removes a client from active connections"""
        # Given: ConnectionManager with a connected client
        await connection_manager.connect(mock_websocket)
        assert len(connection_manager.active_connections) == 1

        # When: Disconnect the client
        await connection_manager.disconnect(mock_websocket)

        # Then: Client should be removed
        assert len(connection_manager.active_connections) == 0
        assert mock_websocket not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_client_doesnt_error(
        self, connection_manager, mock_websocket
    ):
        """Test that disconnecting a non-connected client doesn't raise an error"""
        # Given: ConnectionManager with no clients
        assert len(connection_manager.active_connections) == 0

        # When: Try to disconnect a client that was never connected
        # Then: Should not raise an error
        await connection_manager.disconnect(mock_websocket)

        # Still no clients
        assert len(connection_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that broadcast() sends message to all connected clients"""
        # Given: Multiple connected clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        assert len(connection_manager.active_connections) == 3

        # When: Broadcast a message
        test_message = {
            "type": "speaker_update",
            "data": {"ip": "192.168.1.100", "volume": 50},
        }
        await connection_manager.broadcast(test_message)

        # Then: All clients should receive the message
        for ws in multiple_mock_websockets:
            messages = ws.get_sent_messages()
            assert len(messages) == 1
            assert messages[0] == test_message

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_connections_doesnt_error(
        self, connection_manager
    ):
        """Test that broadcasting with no connections doesn't raise an error"""
        # Given: ConnectionManager with no clients
        assert len(connection_manager.active_connections) == 0

        # When: Try to broadcast
        test_message = {"type": "test", "data": {}}

        # Then: Should not raise an error
        await connection_manager.broadcast(test_message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected_clients(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that broadcast() removes clients that fail to receive messages"""
        # Given: Multiple connected clients, one will fail
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        # Make the second client raise an exception when sending
        failed_client = multiple_mock_websockets[1]
        failed_client.send_text = AsyncMock(side_effect=RuntimeError("Connection lost"))

        assert len(connection_manager.active_connections) == 3

        # When: Broadcast a message
        test_message = {"type": "test", "data": {}}
        await connection_manager.broadcast(test_message)

        # Then: Failed client should be removed, others should receive message
        assert len(connection_manager.active_connections) == 2
        assert failed_client not in connection_manager.active_connections

        # Other clients should have received the message
        for ws in [multiple_mock_websockets[0], multiple_mock_websockets[2]]:
            messages = ws.get_sent_messages()
            assert len(messages) == 1

    @pytest.mark.asyncio
    async def test_send_to_client_sends_to_specific_client(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that send_to_client() sends message to only one specific client"""
        # Given: Multiple connected clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        target_client = multiple_mock_websockets[1]

        # When: Send message to specific client
        test_message = {
            "type": "fade_progress",
            "data": {"progress": 50, "current_volume": 25},
        }
        await connection_manager.send_to_client(target_client, test_message)

        # Then: Only target client should receive the message
        assert len(target_client.get_sent_messages()) == 1
        assert target_client.get_sent_messages()[0] == test_message

        # Other clients should not receive anything
        for ws in [multiple_mock_websockets[0], multiple_mock_websockets[2]]:
            assert len(ws.get_sent_messages()) == 0

    @pytest.mark.asyncio
    async def test_send_to_disconnected_client_removes_it(
        self, connection_manager, mock_websocket
    ):
        """Test that sending to a disconnected client removes it from connections"""
        # Given: Connected client that will fail
        await connection_manager.connect(mock_websocket)
        mock_websocket.send_text = AsyncMock(
            side_effect=RuntimeError("Connection lost")
        )

        assert len(connection_manager.active_connections) == 1

        # When: Try to send to the client
        test_message = {"type": "test", "data": {}}
        await connection_manager.send_to_client(mock_websocket, test_message)

        # Then: Client should be removed
        assert len(connection_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_get_connection_count(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that get_connection_count() returns correct number of connections"""
        # Given: ConnectionManager with no clients
        assert connection_manager.get_connection_count() == 0

        # When: Connect multiple clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        # Then: Should return correct count
        assert connection_manager.get_connection_count() == 3

        # When: Disconnect one client
        await connection_manager.disconnect(multiple_mock_websockets[0])

        # Then: Count should decrease
        assert connection_manager.get_connection_count() == 2

    @pytest.mark.asyncio
    async def test_disconnect_all_removes_all_clients(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that disconnect_all() removes all clients"""
        # Given: Multiple connected clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        assert connection_manager.get_connection_count() == 3

        # When: Disconnect all clients
        await connection_manager.disconnect_all()

        # Then: No clients should remain
        assert connection_manager.get_connection_count() == 0
        assert len(connection_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_all_handles_close_errors(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that disconnect_all() handles errors when closing websockets"""
        # Given: Connected clients, one that will fail to close
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        # Make one client raise an error when closing
        multiple_mock_websockets[1].close = AsyncMock(
            side_effect=RuntimeError("Close failed")
        )

        assert connection_manager.get_connection_count() == 3

        # When: Disconnect all clients (should not raise despite error)
        await connection_manager.disconnect_all()

        # Then: All clients should still be removed
        assert connection_manager.get_connection_count() == 0


class TestMessageTypes:
    """Test different message type formats"""

    @pytest.mark.asyncio
    async def test_speaker_update_message_format(
        self, connection_manager, mock_websocket
    ):
        """Test speaker_update message type"""
        await connection_manager.connect(mock_websocket)

        message = {
            "type": "speaker_update",
            "data": {
                "ip": "192.168.1.100",
                "name": "Living Room",
                "volume": 50,
                "is_playing": True,
            },
        }

        await connection_manager.broadcast(message)

        received = mock_websocket.get_sent_messages()
        assert len(received) == 1
        assert received[0]["type"] == "speaker_update"
        assert "ip" in received[0]["data"]
        assert "volume" in received[0]["data"]

    @pytest.mark.asyncio
    async def test_fade_progress_message_format(
        self, connection_manager, mock_websocket
    ):
        """Test fade_progress message type"""
        await connection_manager.connect(mock_websocket)

        message = {
            "type": "fade_progress",
            "data": {
                "ip": "192.168.1.100",
                "progress": 75,
                "current_volume": 38,
                "target_volume": 50,
            },
        }

        await connection_manager.broadcast(message)

        received = mock_websocket.get_sent_messages()
        assert len(received) == 1
        assert received[0]["type"] == "fade_progress"
        assert received[0]["data"]["progress"] == 75

    @pytest.mark.asyncio
    async def test_tts_started_message_format(self, connection_manager, mock_websocket):
        """Test tts_started message type"""
        await connection_manager.connect(mock_websocket)

        message = {
            "type": "tts_started",
            "data": {
                "text": "Hello world",
                "speaker_ip": "192.168.1.100",
                "audio_url": "http://192.168.1.50:8000/static/audio/test.mp3",
            },
        }

        await connection_manager.broadcast(message)

        received = mock_websocket.get_sent_messages()
        assert len(received) == 1
        assert received[0]["type"] == "tts_started"
        assert "audio_url" in received[0]["data"]

    @pytest.mark.asyncio
    async def test_error_message_format(self, connection_manager, mock_websocket):
        """Test error message type"""
        await connection_manager.connect(mock_websocket)

        message = {
            "type": "error",
            "data": {
                "error_code": "SPEAKER_UNREACHABLE",
                "message": "Cannot connect to speaker",
                "speaker_ip": "192.168.1.100",
            },
        }

        await connection_manager.broadcast(message)

        received = mock_websocket.get_sent_messages()
        assert len(received) == 1
        assert received[0]["type"] == "error"
        assert "error_code" in received[0]["data"]


class TestConcurrency:
    """Test concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test that multiple concurrent broadcasts work correctly"""
        import asyncio

        # Given: Multiple connected clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)

        # When: Send multiple broadcasts concurrently
        async def send_broadcast(msg_num: int):
            message = {"type": "test", "data": {"num": msg_num}}
            await connection_manager.broadcast(message)

        # Send 5 broadcasts concurrently
        await asyncio.gather(*[send_broadcast(i) for i in range(5)])

        # Then: All clients should receive all 5 messages
        for ws in multiple_mock_websockets:
            messages = ws.get_sent_messages()
            assert len(messages) == 5
            # Check that all message numbers are present
            nums = sorted([msg["data"]["num"] for msg in messages])
            assert nums == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_connect_disconnect_during_broadcast(
        self, connection_manager, multiple_mock_websockets
    ):
        """Test connecting/disconnecting clients while broadcasting"""
        import asyncio

        # Given: One connected client
        await connection_manager.connect(multiple_mock_websockets[0])

        # When: Broadcast while adding/removing clients
        async def broadcast_loop():
            for i in range(10):
                message = {"type": "test", "data": {"num": i}}
                await connection_manager.broadcast(message)
                await asyncio.sleep(0.01)

        async def modify_connections():
            await asyncio.sleep(0.02)
            await connection_manager.connect(multiple_mock_websockets[1])
            await asyncio.sleep(0.02)
            await connection_manager.disconnect(multiple_mock_websockets[0])
            await asyncio.sleep(0.02)
            await connection_manager.connect(multiple_mock_websockets[2])

        # Run both operations concurrently
        await asyncio.gather(broadcast_loop(), modify_connections())

        # Then: Should not crash and final state should be correct
        assert len(connection_manager.active_connections) == 2
        assert multiple_mock_websockets[0] not in connection_manager.active_connections
        assert multiple_mock_websockets[1] in connection_manager.active_connections
        assert multiple_mock_websockets[2] in connection_manager.active_connections


class TestHelperFunctions:
    """Test message helper functions"""

    def test_create_speaker_update_message(self):
        """Test speaker_update message helper"""
        from app.services.websocket_manager import create_speaker_update_message

        # With all parameters
        msg = create_speaker_update_message(
            ip="192.168.1.100", name="Living Room", volume=50, is_playing=True
        )

        assert msg["type"] == "speaker_update"
        assert msg["data"]["ip"] == "192.168.1.100"
        assert msg["data"]["name"] == "Living Room"
        assert msg["data"]["volume"] == 50
        assert msg["data"]["is_playing"] is True

        # With only IP (minimal)
        msg = create_speaker_update_message(ip="192.168.1.100")
        assert msg["type"] == "speaker_update"
        assert msg["data"]["ip"] == "192.168.1.100"
        assert "name" not in msg["data"]
        assert "volume" not in msg["data"]

        # With extra kwargs
        msg = create_speaker_update_message(
            ip="192.168.1.100", custom_field="custom_value"
        )
        assert msg["data"]["custom_field"] == "custom_value"

    def test_create_fade_progress_message(self):
        """Test fade_progress message helper"""
        from app.services.websocket_manager import create_fade_progress_message

        msg = create_fade_progress_message(
            ip="192.168.1.100", progress=75, current_volume=38, target_volume=50
        )

        assert msg["type"] == "fade_progress"
        assert msg["data"]["ip"] == "192.168.1.100"
        assert msg["data"]["progress"] == 75
        assert msg["data"]["current_volume"] == 38
        assert msg["data"]["target_volume"] == 50

        # With extra kwargs
        msg = create_fade_progress_message(
            ip="192.168.1.100",
            progress=50,
            current_volume=25,
            target_volume=50,
            duration_ms=1000,
        )
        assert msg["data"]["duration_ms"] == 1000

    def test_create_tts_started_message(self):
        """Test tts_started message helper"""
        from app.services.websocket_manager import create_tts_started_message

        msg = create_tts_started_message(
            text="Hello world",
            speaker_ip="192.168.1.100",
            audio_url="http://192.168.1.50:8000/static/audio/test.mp3",
        )

        assert msg["type"] == "tts_started"
        assert msg["data"]["text"] == "Hello world"
        assert msg["data"]["speaker_ip"] == "192.168.1.100"
        assert (
            msg["data"]["audio_url"] == "http://192.168.1.50:8000/static/audio/test.mp3"
        )

        # With extra kwargs
        msg = create_tts_started_message(
            text="Test",
            speaker_ip="192.168.1.100",
            audio_url="http://test.mp3",
            voice="Rachel",
        )
        assert msg["data"]["voice"] == "Rachel"

    def test_create_error_message(self):
        """Test error message helper"""
        from app.services.websocket_manager import create_error_message

        msg = create_error_message(
            error_code="SPEAKER_UNREACHABLE", message="Cannot connect to speaker"
        )

        assert msg["type"] == "error"
        assert msg["data"]["error_code"] == "SPEAKER_UNREACHABLE"
        assert msg["data"]["message"] == "Cannot connect to speaker"

        # With extra kwargs
        msg = create_error_message(
            error_code="INVALID_VOLUME",
            message="Volume must be 0-100",
            speaker_ip="192.168.1.100",
            attempted_volume=150,
        )
        assert msg["data"]["speaker_ip"] == "192.168.1.100"
        assert msg["data"]["attempted_volume"] == 150
