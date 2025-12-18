"""Standard error response format and utilities for the API."""
from datetime import datetime, timezone
from typing import Dict, Any
from enum import Enum
from fastapi import HTTPException


class ErrorCode(str, Enum):
    """Standard error codes for API responses."""

    # Speaker-related errors
    SPEAKER_UNREACHABLE = "SPEAKER_UNREACHABLE"
    SPEAKER_NOT_FOUND = "SPEAKER_NOT_FOUND"

    # Validation errors
    INVALID_VOLUME = "INVALID_VOLUME"
    INVALID_IP = "INVALID_IP"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # TTS-related errors
    TTS_ERROR = "TTS_ERROR"
    TTS_GENERATION_FAILED = "TTS_GENERATION_FAILED"
    INVALID_API_KEY = "INVALID_API_KEY"
    INVALID_VOICE = "INVALID_VOICE"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # File operations
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"

    # Concurrency
    CONCURRENT_OPERATION = "CONCURRENT_OPERATION"

    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def error_response(message: str, error_code: str | ErrorCode) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.

    Args:
        message: Human-readable error message
        error_code: Error code from ErrorCode enum or string

    Returns:
        Dictionary with standard error format:
        {
            "detail": "Error message",
            "error_code": "ERROR_CODE",
            "timestamp": "2024-12-10T21:00:00Z"
        }
    """
    if isinstance(error_code, ErrorCode):
        error_code = error_code.value

    return {
        "detail": message,
        "error_code": error_code,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def create_error_response(
    message: str,
    error_code: str | ErrorCode,
    status_code: int = 500
) -> HTTPException:
    """
    Create a FastAPI HTTPException with standardized error format.

    Args:
        message: Human-readable error message
        error_code: Error code from ErrorCode enum or string
        status_code: HTTP status code (default: 500)

    Returns:
        HTTPException with error_response as detail

    Example:
        raise create_error_response(
            status_code=404,
            message="Speaker not found at 192.168.1.100",
            error_code=ErrorCode.SPEAKER_UNREACHABLE
        )
    """
    return HTTPException(
        status_code=status_code,
        detail=error_response(message, error_code)
    )


# Convenience functions for common error scenarios
def speaker_unreachable_error(ip: str) -> HTTPException:
    """Create a 503 error for unreachable speaker."""
    return create_error_response(
        status_code=503,
        message=f"Cannot connect to speaker at {ip}",
        error_code=ErrorCode.SPEAKER_UNREACHABLE
    )


def invalid_volume_error(volume: int) -> HTTPException:
    """Create a 400 error for invalid volume."""
    return create_error_response(
        status_code=400,
        message=f"Volume {volume} is invalid. Must be between 0 and 100.",
        error_code=ErrorCode.INVALID_VOLUME
    )


def tts_generation_error(reason: str = "Unknown error") -> HTTPException:
    """Create a 500 error for TTS generation failure."""
    return create_error_response(
        status_code=500,
        message=f"Failed to generate TTS audio: {reason}",
        error_code=ErrorCode.TTS_GENERATION_FAILED
    )


def invalid_api_key_error() -> HTTPException:
    """Create a 401 error for invalid API key."""
    return create_error_response(
        status_code=401,
        message="Invalid or missing API key",
        error_code=ErrorCode.INVALID_API_KEY
    )


def rate_limit_error() -> HTTPException:
    """Create a 429 error for rate limiting."""
    return create_error_response(
        status_code=429,
        message="Rate limit exceeded. Please try again later.",
        error_code=ErrorCode.RATE_LIMIT_EXCEEDED
    )


def file_not_found_error(filename: str) -> HTTPException:
    """Create a 404 error for missing file."""
    return create_error_response(
        status_code=404,
        message=f"File not found: {filename}",
        error_code=ErrorCode.FILE_NOT_FOUND
    )


def concurrent_operation_error(resource: str) -> HTTPException:
    """Create a 409 error for concurrent operation conflict."""
    return create_error_response(
        status_code=409,
        message=f"Another operation is already in progress on {resource}",
        error_code=ErrorCode.CONCURRENT_OPERATION
    )
