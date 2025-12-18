"""Async helper utilities for wrapping synchronous operations."""
import asyncio
from typing import TypeVar, Callable, Any
from functools import wraps

T = TypeVar('T')


async def run_in_thread(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Execute a synchronous function in a thread pool to avoid blocking the event loop.

    This is essential for wrapping blocking I/O operations (like soco library calls)
    so they don't block the async event loop.

    Args:
        func: The synchronous function to execute
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The return value from the synchronous function

    Raises:
        Any exception raised by the synchronous function

    Example:
        async def get_speaker_volume(ip: str) -> int:
            speaker = soco.SoCo(ip)
            # Wrap blocking call in thread pool
            return await run_in_thread(lambda: speaker.volume)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def async_wrap(func: Callable[..., T]) -> Callable[..., Any]:
    """
    Decorator to automatically wrap synchronous functions for async execution.

    Args:
        func: The synchronous function to wrap

    Returns:
        An async function that executes the original in a thread pool

    Example:
        @async_wrap
        def blocking_operation(x: int) -> int:
            time.sleep(1)
            return x * 2

        # Can now be awaited
        result = await blocking_operation(5)
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await run_in_thread(func, *args, **kwargs)

    return wrapper
