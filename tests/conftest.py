"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add app directory to Python path for imports
app_path = Path(__file__).parent.parent
sys.path.insert(0, str(app_path))


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure async backend for pytest-asyncio"""
    return "asyncio"
