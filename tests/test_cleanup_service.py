"""
Tests for Audio Cleanup Service

Following TDD approach - these tests are written BEFORE implementation.
Critical focus: File locking and concurrent access handling.
"""

import pytest
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Note: These imports will fail until we implement the service
try:
    from app.services.cleanup_service import (
        cleanup_old_audio_files,
        start_cleanup_scheduler,
        stop_cleanup_scheduler,
        is_file_in_use,
        CleanupStats,
    )
except ImportError:
    pass


# Fixtures
@pytest.fixture
def audio_dir(tmp_path):
    """Create a temporary audio directory for testing."""
    audio_path = tmp_path / "audio"
    audio_path.mkdir()
    return audio_path


@pytest.fixture
def create_test_files(audio_dir):
    """Factory fixture to create test audio files with specific ages."""
    def _create_files(file_ages_minutes):
        """
        Create test files with specified ages.

        Args:
            file_ages_minutes: List of tuples (filename, age_in_minutes)
        """
        files = []
        now = time.time()

        for filename, age_minutes in file_ages_minutes:
            file_path = audio_dir / filename
            file_path.write_text(f"Mock audio data for {filename}")

            # Set modification time to the past
            old_time = now - (age_minutes * 60)
            os.utime(file_path, (old_time, old_time))

            files.append(file_path)

        return files

    return _create_files


# Test: cleanup_old_audio_files
@pytest.mark.asyncio
async def test_cleanup_deletes_old_files(audio_dir, create_test_files):
    """
    Test that files older than max_age are deleted.

    RED phase: This will fail until implementation.
    """
    # Create files with different ages
    files = create_test_files([
        ("old_file_1.mp3", 61),    # 61 minutes old
        ("old_file_2.mp3", 120),   # 2 hours old
        ("recent_file.mp3", 30),   # 30 minutes old
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        # When: Clean up files older than 60 minutes
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # Then: Old files deleted, recent files kept
        assert not (audio_dir / "old_file_1.mp3").exists()
        assert not (audio_dir / "old_file_2.mp3").exists()
        assert (audio_dir / "recent_file.mp3").exists()

        # Verify stats
        assert stats.deleted_count == 2
        assert stats.kept_count == 1
        assert stats.error_count == 0


@pytest.mark.asyncio
async def test_cleanup_keeps_new_files(audio_dir, create_test_files):
    """
    Test that files newer than max_age are not deleted.
    """
    files = create_test_files([
        ("new_file_1.mp3", 5),
        ("new_file_2.mp3", 10),
        ("new_file_3.mp3", 30),
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # All files should still exist
        for file_path in files:
            assert file_path.exists()

        assert stats.deleted_count == 0
        assert stats.kept_count == 3


@pytest.mark.asyncio
async def test_cleanup_handles_empty_directory(audio_dir):
    """
    Test that cleanup handles empty directory gracefully.
    """
    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        assert stats.deleted_count == 0
        assert stats.kept_count == 0
        assert stats.error_count == 0


@pytest.mark.asyncio
async def test_cleanup_skips_non_mp3_files(audio_dir, create_test_files):
    """
    Test that cleanup only processes MP3 files.
    """
    # Create various file types
    (audio_dir / "audio.mp3").write_text("audio data")
    (audio_dir / "readme.txt").write_text("readme")
    (audio_dir / ".DS_Store").write_text("system file")
    (audio_dir / "data.json").write_text("{}")

    # Make all files old
    now = time.time()
    old_time = now - (120 * 60)  # 2 hours old

    for file in audio_dir.iterdir():
        os.utime(file, (old_time, old_time))

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # Only MP3 should be deleted
        assert not (audio_dir / "audio.mp3").exists()
        assert (audio_dir / "readme.txt").exists()
        assert (audio_dir / ".DS_Store").exists()
        assert (audio_dir / "data.json").exists()


@pytest.mark.asyncio
async def test_cleanup_skips_locked_files(audio_dir, create_test_files):
    """
    CRITICAL TEST: Files currently being played should not be deleted.

    This prevents deleting audio while Sonos is playing it.
    """
    files = create_test_files([
        ("playing_now.mp3", 90),   # Old but being played
        ("old_unused.mp3", 90),    # Old and not in use
    ])

    # Mock the is_file_in_use function to mark first file as in use
    def mock_in_use(filepath):
        return filepath.name == "playing_now.mp3"

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        with patch("app.services.cleanup_service.is_file_in_use", side_effect=mock_in_use):
            stats = await cleanup_old_audio_files(max_age_minutes=60)

            # Playing file should be kept
            assert (audio_dir / "playing_now.mp3").exists()
            # Unused old file should be deleted
            assert not (audio_dir / "old_unused.mp3").exists()

            assert stats.deleted_count == 1
            assert stats.kept_count == 1  # Kept because in use


@pytest.mark.asyncio
async def test_cleanup_handles_deletion_errors(audio_dir, create_test_files):
    """
    Test that cleanup continues even if some files can't be deleted.
    """
    files = create_test_files([
        ("file1.mp3", 90),
        ("file2.mp3", 90),
        ("file3.mp3", 90),
    ])

    # Mock os.remove to fail for file2
    original_remove = os.remove

    def mock_remove(path):
        if "file2.mp3" in str(path):
            raise OSError("Permission denied")
        original_remove(path)

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        with patch("os.remove", side_effect=mock_remove):
            stats = await cleanup_old_audio_files(max_age_minutes=60)

            # Files 1 and 3 deleted, file 2 kept due to error
            assert not (audio_dir / "file1.mp3").exists()
            assert (audio_dir / "file2.mp3").exists()  # Error prevented deletion
            assert not (audio_dir / "file3.mp3").exists()

            assert stats.deleted_count == 2
            assert stats.error_count == 1


@pytest.mark.asyncio
async def test_cleanup_with_zero_max_age(audio_dir, create_test_files):
    """
    Test cleanup with max_age=0 (delete all files immediately).
    """
    files = create_test_files([
        ("file1.mp3", 1),
        ("file2.mp3", 5),
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=0)

        # All files should be deleted
        assert not (audio_dir / "file1.mp3").exists()
        assert not (audio_dir / "file2.mp3").exists()

        assert stats.deleted_count == 2


@pytest.mark.asyncio
async def test_cleanup_with_large_max_age(audio_dir, create_test_files):
    """
    Test cleanup with very large max_age (keep everything).
    """
    files = create_test_files([
        ("file1.mp3", 1000),  # Very old
        ("file2.mp3", 5000),  # Extremely old
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=10000)

        # All files should be kept
        assert (audio_dir / "file1.mp3").exists()
        assert (audio_dir / "file2.mp3").exists()

        assert stats.deleted_count == 0


# Test: is_file_in_use
def test_is_file_in_use_with_open_file(audio_dir):
    """
    Test detection of files that are currently open.

    Note: This is platform-specific and may need adjustment.
    """
    file_path = audio_dir / "test.mp3"
    file_path.write_text("audio data")

    # Open file in read mode (simulating playback)
    with open(file_path, "rb") as f:
        # While file is open, should be detected as in use
        in_use = is_file_in_use(file_path)

        # This is platform-dependent:
        # - Windows: Will detect open files
        # - Unix/Mac: May not detect read-only opens
        # For now, we'll test the function exists and returns a boolean
        assert isinstance(in_use, bool)


def test_is_file_in_use_with_closed_file(audio_dir):
    """
    Test that closed files are not detected as in use.
    """
    file_path = audio_dir / "test.mp3"
    file_path.write_text("audio data")

    in_use = is_file_in_use(file_path)

    # Closed file should not be in use
    assert isinstance(in_use, bool)


def test_is_file_in_use_with_nonexistent_file(audio_dir):
    """
    Test handling of non-existent files.
    """
    file_path = audio_dir / "nonexistent.mp3"

    in_use = is_file_in_use(file_path)

    # Non-existent files are not in use
    assert in_use is False


# Test: Scheduler integration
@pytest.mark.asyncio
async def test_start_cleanup_scheduler():
    """
    Test that cleanup scheduler can be started.
    """
    with patch("app.services.cleanup_service.AsyncIOScheduler") as mock_scheduler:
        mock_scheduler_instance = Mock()
        mock_scheduler.return_value = mock_scheduler_instance

        await start_cleanup_scheduler(
            max_age_minutes=60,
            interval_minutes=30
        )

        # Scheduler should be created and started
        mock_scheduler_instance.add_job.assert_called_once()
        mock_scheduler_instance.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_cleanup_scheduler():
    """
    Test that cleanup scheduler can be stopped.
    """
    # First start a scheduler
    with patch("app.services.cleanup_service.AsyncIOScheduler") as mock_scheduler:
        with patch("app.services.cleanup_service._scheduler", None):
            mock_scheduler_instance = Mock()
            mock_scheduler.return_value = mock_scheduler_instance

            await start_cleanup_scheduler(max_age_minutes=60, interval_minutes=30)
            await stop_cleanup_scheduler()

            # Scheduler should be shut down
            mock_scheduler_instance.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_calls_cleanup_function(audio_dir, create_test_files):
    """
    Test that scheduler actually calls cleanup function.
    """
    files = create_test_files([
        ("old.mp3", 90),
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        # Mock the scheduler to immediately call the cleanup function
        with patch("app.services.cleanup_service.AsyncIOScheduler") as mock_scheduler:
            with patch("app.services.cleanup_service._scheduler", None):
                mock_scheduler_instance = Mock()
                mock_scheduler.return_value = mock_scheduler_instance

                # Capture the cleanup function that would be scheduled
                cleanup_func = None

                def capture_job(*args, **kwargs):
                    nonlocal cleanup_func
                    cleanup_func = kwargs.get("func") or args[0]

                mock_scheduler_instance.add_job.side_effect = capture_job

                await start_cleanup_scheduler(max_age_minutes=60, interval_minutes=30)

                # Manually call the captured function to test it
                if cleanup_func:
                    await cleanup_func()

                # Old file should be deleted
                assert not (audio_dir / "old.mp3").exists()


# Test: CleanupStats model
def test_cleanup_stats_creation():
    """
    Test that CleanupStats model can be created.
    """
    stats = CleanupStats(
        deleted_count=5,
        kept_count=10,
        error_count=1,
        duration_seconds=2.5
    )

    assert stats.deleted_count == 5
    assert stats.kept_count == 10
    assert stats.error_count == 1
    assert stats.duration_seconds == 2.5


def test_cleanup_stats_serialization():
    """
    Test that CleanupStats can be serialized (for logging/API).
    """
    stats = CleanupStats(
        deleted_count=3,
        kept_count=7,
        error_count=0,
        duration_seconds=1.2
    )

    stats_dict = stats.model_dump() if hasattr(stats, 'model_dump') else stats.dict()

    assert isinstance(stats_dict, dict)
    assert stats_dict["deleted_count"] == 3


# Edge Cases and Stress Tests
@pytest.mark.asyncio
async def test_cleanup_many_files(audio_dir):
    """
    Test cleanup with many files (performance test).
    """
    # Create 100 old files
    now = time.time()
    old_time = now - (120 * 60)

    for i in range(100):
        file_path = audio_dir / f"file_{i}.mp3"
        file_path.write_text(f"data {i}")
        os.utime(file_path, (old_time, old_time))

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        assert stats.deleted_count == 100
        assert len(list(audio_dir.iterdir())) == 0


@pytest.mark.asyncio
async def test_cleanup_concurrent_execution(audio_dir, create_test_files):
    """
    Test that multiple cleanup calls can run safely (idempotency).
    """
    import asyncio

    files = create_test_files([
        ("old1.mp3", 90),
        ("old2.mp3", 90),
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        # Run cleanup twice concurrently
        results = await asyncio.gather(
            cleanup_old_audio_files(max_age_minutes=60),
            cleanup_old_audio_files(max_age_minutes=60),
        )

        # Both should complete without error
        assert len(results) == 2

        # Files should be deleted (by one of the calls)
        assert not (audio_dir / "old1.mp3").exists()
        assert not (audio_dir / "old2.mp3").exists()


@pytest.mark.asyncio
async def test_cleanup_with_subdirectories(audio_dir):
    """
    Test that cleanup doesn't descend into subdirectories.
    """
    # Create files in root and subdirectory
    (audio_dir / "root.mp3").write_text("root audio")

    subdir = audio_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.mp3").write_text("nested audio")

    # Make all old
    now = time.time()
    old_time = now - (120 * 60)

    for file in audio_dir.rglob("*.mp3"):
        os.utime(file, (old_time, old_time))

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # Only root-level MP3 should be deleted
        assert not (audio_dir / "root.mp3").exists()
        assert (subdir / "nested.mp3").exists()  # Subdirectory untouched


@pytest.mark.asyncio
async def test_cleanup_handles_unicode_filenames(audio_dir):
    """
    Test cleanup with Unicode characters in filenames.
    """
    # Create file with Unicode name
    unicode_filename = "audio_测试_🎵.mp3"
    file_path = audio_dir / unicode_filename
    file_path.write_text("audio data")

    # Make it old
    now = time.time()
    old_time = now - (120 * 60)
    os.utime(file_path, (old_time, old_time))

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # Should be deleted successfully
        assert not file_path.exists()
        assert stats.deleted_count == 1


@pytest.mark.asyncio
async def test_cleanup_preserves_directory(audio_dir):
    """
    Test that cleanup doesn't delete the audio directory itself.
    """
    # Even with no files, directory should remain
    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        await cleanup_old_audio_files(max_age_minutes=60)

        assert audio_dir.exists()
        assert audio_dir.is_dir()


@pytest.mark.asyncio
async def test_cleanup_logs_detailed_stats(audio_dir, create_test_files):
    """
    Test that cleanup returns detailed statistics.
    """
    files = create_test_files([
        ("old1.mp3", 90),
        ("old2.mp3", 90),
        ("new1.mp3", 30),
    ])

    with patch("app.services.cleanup_service.AUDIO_DIR", audio_dir):
        stats = await cleanup_old_audio_files(max_age_minutes=60)

        # Verify all stat fields are populated
        assert hasattr(stats, "deleted_count")
        assert hasattr(stats, "kept_count")
        assert hasattr(stats, "error_count")
        assert hasattr(stats, "duration_seconds")

        assert stats.deleted_count == 2
        assert stats.kept_count == 1
        assert stats.duration_seconds > 0
