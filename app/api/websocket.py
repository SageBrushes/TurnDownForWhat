"""
WebSocket API endpoint for real-time updates.

Provides WebSocket connection at /ws for receiving real-time updates about:
- Speaker state changes (volume, playback status)
- Volume fade progress
- TTS playback events
- Error notifications
"""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any

from app.services.websocket_manager import get_connection_manager


logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time client updates.

    Clients connect to this endpoint to receive real-time notifications about:
    - speaker_update: Speaker state changes (volume, playback, etc.)
    - fade_progress: Volume fade operation progress
    - tts_started: TTS audio playback initiated
    - error: Error notifications

    The endpoint also supports ping-pong for keepalive.

    Message Format (Server -> Client):
        {
            "type": "connection|speaker_update|fade_progress|tts_started|error|pong",
            "data": { ... },
            "message": "..."  # Optional for connection/error types
        }

    Message Format (Client -> Server):
        {
            "type": "ping|...",
            "data": { ... }  # Optional
        }

    Args:
        websocket: FastAPI WebSocket connection

    Example:
        # JavaScript client
        const ws = new WebSocket('ws://localhost:8000/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data.type, data.data);
        };
    """
    manager = get_connection_manager()

    # Accept the WebSocket connection
    await websocket.accept()
    logger.info(f"WebSocket client connected")

    # Register connection with manager
    await manager.connect(websocket)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to Sonos TTS WebSocket"
        })

        # Listen for client messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()

                # Parse JSON
                try:
                    message = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Invalid JSON: {str(e)}"
                    })
                    continue

                # Handle different message types
                message_type = message.get("type", "unknown")

                if message_type == "ping":
                    # Respond to ping with pong
                    await websocket.send_json({"type": "pong"})
                    logger.debug("Ping-pong keepalive")

                elif message_type == "test":
                    # Echo test messages (useful for debugging)
                    await websocket.send_json({
                        "type": "test_response",
                        "data": message.get("data", {})
                    })
                    logger.debug("Test message echoed")

                else:
                    # Unknown message type - acknowledge but don't process
                    logger.debug(f"Received unknown message type: {message_type}")
                    await websocket.send_json({
                        "type": "ack",
                        "message": f"Received {message_type}"
                    })

            except json.JSONDecodeError as e:
                # This shouldn't happen as we catch it above, but just in case
                logger.warning(f"JSON decode error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })

            except WebSocketDisconnect:
                # Client disconnected
                logger.info("Client disconnected normally")
                break

            except Exception as e:
                # Unexpected error while processing message
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing message: {str(e)}"
                    })
                except:
                    # If we can't send the error, connection is likely broken
                    break

    except WebSocketDisconnect:
        # Client disconnected
        logger.info("Client disconnected during connection")

    except Exception as e:
        # Unexpected error
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        # Always clean up the connection
        await manager.disconnect(websocket)
        logger.info(
            f"WebSocket client disconnected. "
            f"Active connections: {manager.get_connection_count()}"
        )
