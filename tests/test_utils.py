"""Tests for utility functions including error responses and async helpers."""
import pytest
from datetime import datetime
import asyncio
import time


def test_error_response_format():
    """Test that error_response creates properly formatted error dict."""
    # When: Create error response
    from app.utils.errors import error_response

    result = error_response("Speaker not found", "SPEAKER_UNREACHABLE")

    # Then: Should have required fields
    assert "detail" in result
    assert "error_code" in result
    assert "timestamp" in result

    assert result["detail"] == "Speaker not found"
    assert result["error_code"] == "SPEAKER_UNREACHABLE"

    # Timestamp should be ISO format string
    assert isinstance(result["timestamp"], str)
    # Should be parseable as datetime
    datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))


def test_error_response_timestamp_is_recent():
    """Test that error_response timestamp is current."""
    # When: Create error response
    from app.utils.errors import error_response
    from datetime import timezone

    before = datetime.now(timezone.utc)
    result = error_response("Test error", "TEST_ERROR")
    after = datetime.now(timezone.utc)

    # Then: Timestamp should be between before and after
    timestamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    assert before <= timestamp <= after


def test_error_response_with_different_codes():
    """Test error_response with various error codes."""
    # Given: Different error scenarios
    from app.utils.errors import error_response, ErrorCode

    test_cases = [
        ("Speaker unreachable", ErrorCode.SPEAKER_UNREACHABLE),
        ("Invalid volume", ErrorCode.INVALID_VOLUME),
        ("TTS failed", ErrorCode.TTS_GENERATION_FAILED),
        ("Rate limit", ErrorCode.RATE_LIMIT_EXCEEDED),
    ]

    # When/Then: Each should produce valid response
    for message, code in test_cases:
        result = error_response(message, code)
        assert result["detail"] == message
        assert result["error_code"] == code


def test_error_code_enum_has_standard_codes():
    """Test that ErrorCode enum has all standard error codes."""
    # When: Import ErrorCode
    from app.utils.errors import ErrorCode

    # Then: Should have all standard codes from spec
    assert hasattr(ErrorCode, "SPEAKER_UNREACHABLE")
    assert hasattr(ErrorCode, "INVALID_VOLUME")
    assert hasattr(ErrorCode, "TTS_GENERATION_FAILED")
    assert hasattr(ErrorCode, "INVALID_API_KEY")
    assert hasattr(ErrorCode, "RATE_LIMIT_EXCEEDED")
    assert hasattr(ErrorCode, "FILE_NOT_FOUND")
    assert hasattr(ErrorCode, "CONCURRENT_OPERATION")


@pytest.mark.asyncio
async def test_run_in_thread_executes_sync_function():
    """Test that run_in_thread wrapper executes synchronous function in thread pool."""
    # Given: A synchronous function
    from app.utils.async_helpers import run_in_thread

    def sync_function(x, y):
        return x + y

    # When: Execute via run_in_thread
    result = await run_in_thread(sync_function, 5, 10)

    # Then: Should return correct result
    assert result == 15


@pytest.mark.asyncio
async def test_run_in_thread_does_not_block_event_loop():
    """Test that run_in_thread doesn't block the async event loop."""
    # Given: A slow synchronous function
    from app.utils.async_helpers import run_in_thread

    def slow_sync_function():
        time.sleep(0.1)
        return "done"

    # When: Run multiple slow functions concurrently
    start = time.time()
    results = await asyncio.gather(
        run_in_thread(slow_sync_function),
        run_in_thread(slow_sync_function),
        run_in_thread(slow_sync_function),
    )
    elapsed = time.time() - start

    # Then: Should complete in parallel (much less than 0.3s serial)
    assert all(r == "done" for r in results)
    assert elapsed < 0.25  # Should be ~0.1s if truly parallel


@pytest.mark.asyncio
async def test_run_in_thread_propagates_exceptions():
    """Test that run_in_thread propagates exceptions from sync function."""
    # Given: A function that raises an exception
    from app.utils.async_helpers import run_in_thread

    def failing_function():
        raise ValueError("Something went wrong")

    # When: Execute via run_in_thread
    # Then: Should propagate the exception
    with pytest.raises(ValueError) as exc_info:
        await run_in_thread(failing_function)

    assert "Something went wrong" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_in_thread_with_kwargs():
    """Test that run_in_thread handles keyword arguments."""
    # Given: A function that uses kwargs
    from app.utils.async_helpers import run_in_thread

    def func_with_kwargs(a, b, c=10):
        return a + b + c

    # When: Call with kwargs
    result = await run_in_thread(func_with_kwargs, 1, 2, c=3)

    # Then: Should pass kwargs correctly
    assert result == 6


def test_create_error_response_helper():
    """Test convenience function for creating FastAPI error responses."""
    # When: Use create_error_response
    from app.utils.errors import create_error_response
    from fastapi import HTTPException

    response = create_error_response(
        status_code=404,
        message="Speaker not found",
        error_code="SPEAKER_UNREACHABLE"
    )

    # Then: Should return HTTPException with proper format
    assert isinstance(response, HTTPException)
    assert response.status_code == 404
    assert isinstance(response.detail, dict)
    assert response.detail["detail"] == "Speaker not found"
    assert response.detail["error_code"] == "SPEAKER_UNREACHABLE"
    assert "timestamp" in response.detail


def test_create_error_response_default_status():
    """Test that create_error_response defaults to 500."""
    # When: Create error without status code
    from app.utils.errors import create_error_response

    response = create_error_response(
        message="Internal error",
        error_code="INTERNAL_ERROR"
    )

    # Then: Should default to 500
    assert response.status_code == 500
