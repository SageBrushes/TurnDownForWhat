"""
WebSocket Connection Manager for real-time updates.

Implements singleton pattern to manage WebSocket connections across the application.
Handles broadcasting messages to all clients and sending to individual clients.

Message Types:
- speaker_update: Speaker state changes (volume, playback status)
- fade_progress: Volume fade progress updates
- tts_started: TTS playback initiated
- error: Error notifications
"""

import json
import logging
from typing import Dict, Set
from fastapi import WebSocket


logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Singleton WebSocket connection manager.

    Manages all active WebSocket connections and provides methods for
    broadcasting messages to all clients or sending to specific clients.

    Automatically handles disconnected clients by removing them when
    message sending fails.
    """

    _instance = None

    def __new__(cls):
        """Implement singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize connection manager (only once due to singleton)"""
        if self._initialized:
            return

        self.active_connections: Set[WebSocket] = set()
        self._initialized = True
        logger.info("ConnectionManager initialized")

    async def connect(self, websocket: WebSocket) -> None:
        """
        Add a client to active connections.

        Args:
            websocket: The WebSocket connection to add

        Example:
            >>> manager = ConnectionManager()
            >>> await manager.connect(websocket)
        """
        self.active_connections.add(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a client from active connections.

        Safely handles removal even if the client was not connected.

        Args:
            websocket: The WebSocket connection to remove

        Example:
            >>> manager = ConnectionManager()
            >>> await manager.disconnect(websocket)
        """
        self.active_connections.discard(websocket)
        logger.info(
            f"Client disconnected. Total connections: {len(self.active_connections)}"
        )

    async def disconnect_all(self) -> None:
        """
        Disconnect all active clients.

        Useful for cleanup during shutdown or testing.

        Example:
            >>> manager = ConnectionManager()
            >>> await manager.disconnect_all()
        """
        for websocket in list(self.active_connections):
            try:
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error closing websocket: {e}")

        self.active_connections.clear()
        logger.info("All clients disconnected")

    async def broadcast(self, message: Dict) -> None:
        """
        Send a message to all connected clients.

        Automatically removes clients that fail to receive the message
        (e.g., due to disconnection).

        Args:
            message: Dictionary containing message data (will be JSON serialized)

        Message Format:
            {
                "type": "speaker_update|fade_progress|tts_started|error",
                "data": { ... message-specific data ... }
            }

        Example:
            >>> manager = ConnectionManager()
            >>> await manager.broadcast({
            ...     "type": "speaker_update",
            ...     "data": {"ip": "192.168.1.100", "volume": 50}
            ... })
        """
        if not self.active_connections:
            logger.debug("No active connections for broadcast")
            return

        # Convert message to JSON
        message_json = json.dumps(message)

        # Track failed connections for removal
        failed_connections = []

        # Send to all clients
        for websocket in self.active_connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to client: {e}")
                failed_connections.append(websocket)

        # Remove failed connections
        for websocket in failed_connections:
            self.active_connections.discard(websocket)
            logger.info(
                f"Removed failed connection. "
                f"Total connections: {len(self.active_connections)}"
            )

        logger.debug(
            f"Broadcast sent to {len(self.active_connections)} clients "
            f"({len(failed_connections)} failed)"
        )

    async def send_to_client(self, websocket: WebSocket, message: Dict) -> None:
        """
        Send a message to a specific client.

        Automatically removes the client if message sending fails.

        Args:
            websocket: The target WebSocket connection
            message: Dictionary containing message data (will be JSON serialized)

        Example:
            >>> manager = ConnectionManager()
            >>> await manager.send_to_client(websocket, {
            ...     "type": "fade_progress",
            ...     "data": {"progress": 50, "current_volume": 25}
            ... })
        """
        try:
            message_json = json.dumps(message)
            await websocket.send_text(message_json)
            logger.debug(f"Message sent to client: {message.get('type')}")
        except Exception as e:
            logger.warning(f"Failed to send message to client: {e}")
            self.active_connections.discard(websocket)
            logger.info(
                f"Removed failed connection. "
                f"Total connections: {len(self.active_connections)}"
            )

    def get_connection_count(self) -> int:
        """
        Get the number of active connections.

        Returns:
            Number of currently connected clients

        Example:
            >>> manager = ConnectionManager()
            >>> count = manager.get_connection_count()
        """
        return len(self.active_connections)


# Helper functions for creating standardized messages


def create_speaker_update_message(
    ip: str, name: str = None, volume: int = None, is_playing: bool = None, **kwargs
) -> Dict:
    """
    Create a speaker_update message.

    Args:
        ip: Speaker IP address
        name: Speaker name (optional)
        volume: Current volume 0-100 (optional)
        is_playing: Playback status (optional)
        **kwargs: Additional data to include

    Returns:
        Formatted message dictionary

    Example:
        >>> msg = create_speaker_update_message(
        ...     ip="192.168.1.100",
        ...     name="Living Room",
        ...     volume=50,
        ...     is_playing=True
        ... )
    """
    data = {"ip": ip}
    if name is not None:
        data["name"] = name
    if volume is not None:
        data["volume"] = volume
    if is_playing is not None:
        data["is_playing"] = is_playing
    data.update(kwargs)

    return {"type": "speaker_update", "data": data}


def create_fade_progress_message(
    ip: str, progress: int, current_volume: int, target_volume: int, **kwargs
) -> Dict:
    """
    Create a fade_progress message.

    Args:
        ip: Speaker IP address
        progress: Fade progress percentage 0-100
        current_volume: Current volume level
        target_volume: Target volume level
        **kwargs: Additional data to include

    Returns:
        Formatted message dictionary

    Example:
        >>> msg = create_fade_progress_message(
        ...     ip="192.168.1.100",
        ...     progress=75,
        ...     current_volume=38,
        ...     target_volume=50
        ... )
    """
    data = {
        "ip": ip,
        "progress": progress,
        "current_volume": current_volume,
        "target_volume": target_volume,
    }
    data.update(kwargs)

    return {"type": "fade_progress", "data": data}


def create_tts_started_message(
    text: str, speaker_ip: str, audio_url: str, **kwargs
) -> Dict:
    """
    Create a tts_started message.

    Args:
        text: The TTS text that was generated
        speaker_ip: Speaker IP address
        audio_url: URL to the generated audio file
        **kwargs: Additional data to include

    Returns:
        Formatted message dictionary

    Example:
        >>> msg = create_tts_started_message(
        ...     text="Hello world",
        ...     speaker_ip="192.168.1.100",
        ...     audio_url="http://192.168.1.50:8000/static/audio/test.mp3"
        ... )
    """
    data = {"text": text, "speaker_ip": speaker_ip, "audio_url": audio_url}
    data.update(kwargs)

    return {"type": "tts_started", "data": data}


def create_error_message(error_code: str, message: str, **kwargs) -> Dict:
    """
    Create an error message.

    Args:
        error_code: Standard error code (e.g., "SPEAKER_UNREACHABLE")
        message: Human-readable error message
        **kwargs: Additional data to include (e.g., speaker_ip)

    Returns:
        Formatted message dictionary

    Example:
        >>> msg = create_error_message(
        ...     error_code="SPEAKER_UNREACHABLE",
        ...     message="Cannot connect to speaker",
        ...     speaker_ip="192.168.1.100"
        ... )
    """
    data = {"error_code": error_code, "message": message}
    data.update(kwargs)

    return {"type": "error", "data": data}


# Singleton accessor
_manager_instance: ConnectionManager = None


def get_connection_manager() -> ConnectionManager:
    """
    Get the singleton ConnectionManager instance.

    Returns:
        The global ConnectionManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ConnectionManager()
    return _manager_instance
