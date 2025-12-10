"""
Pytest configuration and shared fixtures for TTS service tests.
"""

import pytest
import sys
from pathlib import Path

# Add app directory to Python path for imports
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test_api_key_12345")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8000")
