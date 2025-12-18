"""
Tests for WebSocket API endpoint.

Tests the WebSocket endpoint handling client connections, messages,
disconnections, and error scenarios.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
import json


@pytest.mark.asyncio
async def test_websocket_connection_lifecycle(app_client):
    """Test WebSocket connection, message exchange, and disconnection."""
    with app_client.websocket_connect("/ws") as websocket:
        # Connection should be established
        assert websocket is not None

        # Should receive a welcome message
        data = websocket.receive_json()
        assert data["type"] == "connection"
        assert data["message"] == "Connected to Sonos TTS WebSocket"


@pytest.mark.asyncio
async def test_websocket_receives_broadcasts(app_client, connection_manager):
    """Test that WebSocket clients receive broadcast messages."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Broadcast a speaker update
        await connection_manager.broadcast({
            "type": "speaker_update",
            "data": {
                "ip": "192.168.1.100",
                "name": "Living Room",
                "volume": 50
            }
        })

        # Should receive the broadcast
        data = websocket.receive_json()
        assert data["type"] == "speaker_update"
        assert data["data"]["ip"] == "192.168.1.100"
        assert data["data"]["name"] == "Living Room"
        assert data["data"]["volume"] == 50


@pytest.mark.asyncio
async def test_websocket_multiple_clients(app_client, connection_manager):
    """Test that broadcasts reach all connected clients."""
    with app_client.websocket_connect("/ws") as ws1, \
         app_client.websocket_connect("/ws") as ws2:

        # Consume welcome messages
        ws1.receive_json()
        ws2.receive_json()

        # Broadcast a message
        await connection_manager.broadcast({
            "type": "fade_progress",
            "data": {
                "ip": "192.168.1.100",
                "progress": 50,
                "current_volume": 25,
                "target_volume": 50
            }
        })

        # Both clients should receive it
        data1 = ws1.receive_json()
        data2 = ws2.receive_json()

        assert data1["type"] == "fade_progress"
        assert data2["type"] == "fade_progress"
        assert data1["data"]["progress"] == 50
        assert data2["data"]["progress"] == 50


@pytest.mark.asyncio
async def test_websocket_ping_pong(app_client):
    """Test WebSocket ping-pong for keepalive."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Send a ping message
        websocket.send_json({"type": "ping"})

        # Should receive a pong response
        data = websocket.receive_json()
        assert data["type"] == "pong"


@pytest.mark.asyncio
async def test_websocket_client_message_echo(app_client):
    """Test that client messages are acknowledged."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Send a test message
        websocket.send_json({
            "type": "test",
            "data": {"key": "value"}
        })

        # Should receive an acknowledgment or echo
        data = websocket.receive_json()
        assert "type" in data


@pytest.mark.asyncio
async def test_websocket_disconnection_cleanup(app_client, connection_manager):
    """Test that disconnected clients are removed from the connection manager."""
    initial_count = connection_manager.get_connection_count()

    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Connection count should increase
        assert connection_manager.get_connection_count() == initial_count + 1

    # After context exit, connection should be cleaned up
    # Give it a moment for cleanup
    import asyncio
    await asyncio.sleep(0.1)

    assert connection_manager.get_connection_count() == initial_count


@pytest.mark.asyncio
async def test_websocket_invalid_json_handling(app_client):
    """Test that invalid JSON is handled gracefully."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Send invalid JSON (as text)
        websocket.send_text("{invalid json}")

        # Should receive an error message
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert "message" in data


@pytest.mark.asyncio
async def test_websocket_connection_manager_integration(app_client, connection_manager):
    """Test that WebSocket endpoint properly integrates with ConnectionManager."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Verify connection is registered
        assert connection_manager.get_connection_count() >= 1


@pytest.mark.asyncio
async def test_websocket_error_broadcast(app_client, connection_manager):
    """Test that error messages are properly broadcast to clients."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Broadcast an error message
        await connection_manager.broadcast({
            "type": "error",
            "data": {
                "error_code": "SPEAKER_UNREACHABLE",
                "message": "Cannot connect to speaker",
                "speaker_ip": "192.168.1.100"
            }
        })

        # Should receive the error
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["data"]["error_code"] == "SPEAKER_UNREACHABLE"


@pytest.mark.asyncio
async def test_websocket_tts_started_broadcast(app_client, connection_manager):
    """Test that tts_started messages are properly broadcast."""
    with app_client.websocket_connect("/ws") as websocket:
        # Consume welcome message
        websocket.receive_json()

        # Broadcast a tts_started message
        await connection_manager.broadcast({
            "type": "tts_started",
            "data": {
                "text": "Hello world",
                "speaker_ip": "192.168.1.100",
                "audio_url": "http://192.168.1.50:8000/static/audio/test.mp3",
                "filename": "test.mp3",
                "voice": "Rachel"
            }
        })

        # Should receive the message
        data = websocket.receive_json()
        assert data["type"] == "tts_started"
        assert data["data"]["text"] == "Hello world"
        assert data["data"]["voice"] == "Rachel"


@pytest.mark.asyncio
async def test_websocket_concurrent_connections(app_client):
    """Test handling of multiple concurrent WebSocket connections."""
    connections = []

    # Create multiple connections
    for i in range(5):
        ws = app_client.websocket_connect("/ws")
        connections.append(ws.__enter__())

    try:
        # Consume welcome messages
        for ws in connections:
            data = ws.receive_json()
            assert data["type"] == "connection"
    finally:
        # Clean up connections
        for i, ws in enumerate(connections):
            try:
                connections[i].__exit__(None, None, None)
            except:
                pass


@pytest.mark.asyncio
async def test_websocket_endpoint_path(app_client):
    """Test that WebSocket endpoint is available at /ws."""
    with app_client.websocket_connect("/ws") as websocket:
        # Connection should succeed
        assert websocket is not None
        data = websocket.receive_json()
        assert "type" in data
