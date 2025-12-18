"""Comprehensive tests for Sonos Service Layer."""
import pytest
import asyncio
import math
from unittest.mock import Mock, patch, AsyncMock, MagicMock, PropertyMock
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.services import sonos_service
from app.utils.errors import ErrorCode


class TestDiscoverSpeakers:
    """Test speaker discovery with caching."""

    @pytest.mark.asyncio
    async def test_discover_speakers_success(self, mock_multiple_speakers):
        """Test successful speaker discovery."""
        with patch("soco.discover", return_value=iter(mock_multiple_speakers)):
            speakers = await sonos_service.discover_speakers()

            assert len(speakers) == 3
            assert speakers[0]["ip"] == "192.168.1.100"
            assert speakers[0]["name"] == "Living Room"
            assert speakers[0]["volume"] == 50
            assert speakers[0]["is_coordinator"] is True

            assert speakers[1]["ip"] == "192.168.1.101"
            assert speakers[2]["ip"] == "192.168.1.102"

    @pytest.mark.asyncio
    async def test_discover_speakers_uses_cache(self, mock_multiple_speakers):
        """Test that discovery uses cache within timeout period."""
        with patch("soco.discover", return_value=iter(mock_multiple_speakers)) as mock_discover:
            # First call - should discover
            speakers1 = await sonos_service.discover_speakers()
            assert mock_discover.call_count == 1

            # Second call - should use cache
            speakers2 = await sonos_service.discover_speakers()
            assert mock_discover.call_count == 1  # Still 1, used cache
            assert speakers1 == speakers2

    @pytest.mark.asyncio
    async def test_discover_speakers_force_refresh(self, mock_multiple_speakers):
        """Test force refresh bypasses cache."""
        with patch("soco.discover", return_value=iter(mock_multiple_speakers)) as mock_discover:
            # First call
            await sonos_service.discover_speakers()
            assert mock_discover.call_count == 1

            # Force refresh - should discover again
            await sonos_service.discover_speakers(force_refresh=True)
            assert mock_discover.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_speakers_cache_expiration(self, mock_multiple_speakers):
        """Test that cache expires after timeout period."""
        with patch("soco.discover", return_value=iter(mock_multiple_speakers)) as mock_discover:
            # First call
            await sonos_service.discover_speakers()
            assert mock_discover.call_count == 1

            # Manually expire cache by setting old timestamp
            sonos_service._cache_timestamp = datetime.now() - timedelta(minutes=10)

            # Should discover again due to expired cache
            await sonos_service.discover_speakers()
            assert mock_discover.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_speakers_empty_result(self):
        """Test discovery with no speakers found."""
        with patch("soco.discover", return_value=iter([])):
            speakers = await sonos_service.discover_speakers()
            assert speakers == []

    @pytest.mark.asyncio
    async def test_discover_speakers_partial_failure(self, mock_multiple_speakers):
        """Test discovery when some speakers fail info gathering."""
        # Make second speaker fail when accessing properties
        type(mock_multiple_speakers[1]).player_name = PropertyMock(side_effect=Exception("Connection error"))

        with patch("soco.discover", return_value=iter(mock_multiple_speakers)):
            speakers = await sonos_service.discover_speakers()

            # Should skip failed speaker but return others
            assert len(speakers) == 2
            assert speakers[0]["ip"] == "192.168.1.100"
            assert speakers[1]["ip"] == "192.168.1.102"

    @pytest.mark.asyncio
    async def test_discover_speakers_complete_failure(self):
        """Test discovery failure raises exception."""
        with patch("soco.discover", side_effect=Exception("Network error")):
            with pytest.raises(Exception) as exc_info:
                await sonos_service.discover_speakers()

            assert "Speaker discovery failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_clear_speaker_cache(self, mock_multiple_speakers):
        """Test clearing speaker cache."""
        with patch("soco.discover", return_value=iter(mock_multiple_speakers)):
            # Populate cache
            await sonos_service.discover_speakers()
            assert len(sonos_service._speaker_cache) > 0
            assert sonos_service._cache_timestamp is not None

            # Clear cache
            await sonos_service.clear_speaker_cache()
            assert len(sonos_service._speaker_cache) == 0
            assert sonos_service._cache_timestamp is None


class TestGetSpeakerStatus:
    """Test getting detailed speaker status."""

    @pytest.mark.asyncio
    async def test_get_speaker_status_success(self, mock_speaker):
        """Test successful status retrieval."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            status = await sonos_service.get_speaker_status("192.168.1.100")

            assert status["ip"] == "192.168.1.100"
            assert status["name"] == "Living Room"
            assert status["volume"] == 50
            assert status["is_playing"] is True
            assert status["is_paused"] is False
            assert status["is_stopped"] is False
            assert status["transport_state"] == "PLAYING"
            assert status["current_track"]["title"] == "Test Track"
            assert status["current_track"]["artist"] == "Test Artist"

    @pytest.mark.asyncio
    async def test_get_speaker_status_paused(self, mock_speaker):
        """Test status when speaker is paused."""
        mock_speaker.get_current_transport_info.return_value = {
            "current_transport_state": "PAUSED_PLAYBACK"
        }

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            status = await sonos_service.get_speaker_status("192.168.1.100")

            assert status["is_playing"] is False
            assert status["is_paused"] is True
            assert status["is_stopped"] is False

    @pytest.mark.asyncio
    async def test_get_speaker_status_stopped(self, mock_speaker):
        """Test status when speaker is stopped."""
        mock_speaker.get_current_transport_info.return_value = {
            "current_transport_state": "STOPPED"
        }

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            status = await sonos_service.get_speaker_status("192.168.1.100")

            assert status["is_playing"] is False
            assert status["is_paused"] is False
            assert status["is_stopped"] is True

    @pytest.mark.asyncio
    async def test_get_speaker_status_unreachable(self):
        """Test status retrieval when speaker is unreachable."""
        mock_speaker = Mock()
        mock_speaker.get_current_transport_info = Mock(
            side_effect=Exception("Connection timeout")
        )

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.get_speaker_status("192.168.1.200")

            assert exc_info.value.status_code == 503
            assert "Cannot connect to speaker" in str(exc_info.value.detail)


class TestSetSpeakerVolume:
    """Test instant volume setting."""

    @pytest.mark.asyncio
    async def test_set_volume_success(self, mock_speaker):
        """Test successful volume setting."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.set_speaker_volume("192.168.1.100", 75)

            assert result["ip"] == "192.168.1.100"
            assert result["volume"] == 75
            assert "Volume set to 75" in result["message"]

    @pytest.mark.asyncio
    async def test_set_volume_minimum(self, mock_speaker):
        """Test setting volume to minimum (0)."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.set_speaker_volume("192.168.1.100", 0)
            assert result["volume"] == 0

    @pytest.mark.asyncio
    async def test_set_volume_maximum(self, mock_speaker):
        """Test setting volume to maximum (100)."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.set_speaker_volume("192.168.1.100", 100)
            assert result["volume"] == 100

    @pytest.mark.asyncio
    async def test_set_volume_invalid_too_high(self):
        """Test setting volume above 100."""
        with pytest.raises(HTTPException) as exc_info:
            await sonos_service.set_speaker_volume("192.168.1.100", 101)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == ErrorCode.INVALID_VOLUME.value

    @pytest.mark.asyncio
    async def test_set_volume_invalid_too_low(self):
        """Test setting volume below 0."""
        with pytest.raises(HTTPException) as exc_info:
            await sonos_service.set_speaker_volume("192.168.1.100", -1)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == ErrorCode.INVALID_VOLUME.value

    @pytest.mark.asyncio
    async def test_set_volume_unreachable_speaker(self):
        """Test volume setting when speaker is unreachable."""
        mock_speaker = Mock()
        # Simulate unreachable by raising exception on property setter
        type(mock_speaker).volume = PropertyMock(side_effect=Exception("Connection timeout"))

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.set_speaker_volume("192.168.1.100", 50)

            assert exc_info.value.status_code == 503


class TestFadeSpeakerVolume:
    """Test volume fading with S-curve algorithm."""

    @pytest.mark.asyncio
    async def test_fade_volume_up(self, mock_speaker):
        """Test fading volume up from 20 to 80."""
        # Track volume changes
        volume_values = []

        def track_volume(v):
            volume_values.append(v)

        # Mock the volume property to track changes
        type(mock_speaker).volume = PropertyMock(
            return_value=20,
            side_effect=lambda v=None: volume_values.append(v) if v is not None else 20
        )

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):  # Speed up test
                result = await sonos_service.fade_speaker_volume("192.168.1.100", 80)

                assert result["ip"] == "192.168.1.100"
                assert result["volume"] == 80
                assert result["direction"] == "up"
                assert result["steps"] > 0

    @pytest.mark.asyncio
    async def test_fade_volume_down(self, mock_speaker):
        """Test fading volume down from 80 to 20."""
        type(mock_speaker).volume = PropertyMock(return_value=80)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                result = await sonos_service.fade_speaker_volume("192.168.1.100", 20)

                assert result["volume"] == 20
                assert result["direction"] == "down"

    @pytest.mark.asyncio
    async def test_fade_already_at_target(self, mock_speaker):
        """Test fade when already at target volume."""
        type(mock_speaker).volume = PropertyMock(return_value=50)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.fade_speaker_volume("192.168.1.100", 50)

            assert result["volume"] == 50
            assert "Already at target volume" in result["message"]

    @pytest.mark.asyncio
    async def test_fade_uses_s_curve_algorithm(self):
        """Test that fade uses S-curve (ease-in-out) algorithm."""
        volume_changes = []

        class MockSpeakerWithTracking:
            def __init__(self):
                self._volume = 0
                self.ip_address = "192.168.1.100"

            @property
            def volume(self):
                return self._volume

            @volume.setter
            def volume(self, v):
                self._volume = v
                volume_changes.append(v)

        mock_speaker = MockSpeakerWithTracking()

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                with patch("app.services.sonos_service.FADE_STEPS", new=10):
                    await sonos_service.fade_speaker_volume("192.168.1.100", 100)

                    # Verify S-curve: changes should be smaller at start/end, larger in middle
                    assert len(volume_changes) > 5

                    # First change should be relatively small (ease-in)
                    first_change = abs(volume_changes[1] - volume_changes[0])
                    # Middle change should be larger
                    mid_idx = len(volume_changes) // 2
                    middle_change = abs(volume_changes[mid_idx] - volume_changes[mid_idx - 1])

                    # Due to S-curve, middle changes should be >= first changes
                    # (with some tolerance for integer rounding)
                    assert middle_change >= first_change - 2

    @pytest.mark.asyncio
    async def test_fade_with_callback(self, mock_speaker):
        """Test fade progress callbacks."""
        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                with patch("app.services.sonos_service.FADE_STEPS", new=5):
                    await sonos_service.fade_speaker_volume(
                        "192.168.1.100", 50, callback=progress_callback
                    )

                    # Should have callbacks for each step
                    assert len(callback_calls) > 0
                    # Last callback should show completion
                    assert callback_calls[-1][0] == callback_calls[-1][1]

    @pytest.mark.asyncio
    async def test_fade_with_async_callback(self, mock_speaker):
        """Test fade with async callback function."""
        callback_calls = []

        async def async_callback(current, total):
            callback_calls.append((current, total))

        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                with patch("app.services.sonos_service.FADE_STEPS", new=5):
                    await sonos_service.fade_speaker_volume(
                        "192.168.1.100", 50, callback=async_callback
                    )

                    assert len(callback_calls) > 0

    @pytest.mark.asyncio
    async def test_fade_callback_error_doesnt_break_fade(self, mock_speaker):
        """Test that callback errors don't break the fade operation."""

        def failing_callback(current, total):
            raise Exception("Callback error")

        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # Should complete despite callback errors
                result = await sonos_service.fade_speaker_volume(
                    "192.168.1.100", 50, callback=failing_callback
                )

                assert result["volume"] == 50

    @pytest.mark.asyncio
    async def test_fade_invalid_volume(self):
        """Test fade with invalid target volume."""
        with pytest.raises(HTTPException) as exc_info:
            await sonos_service.fade_speaker_volume("192.168.1.100", 150)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == ErrorCode.INVALID_VOLUME.value

    @pytest.mark.asyncio
    async def test_fade_speaker_unreachable_at_start(self):
        """Test fade when speaker is unreachable from the start."""
        mock_speaker = Mock()
        type(mock_speaker).volume = PropertyMock(side_effect=Exception("Connection timeout"))

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.fade_speaker_volume("192.168.1.100", 50)

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_fade_speaker_disconnects_during_fade(self, mock_speaker):
        """CRITICAL: Test speaker becoming unreachable DURING volume fade."""
        call_count = [0]

        def volume_getter():
            return 0

        def volume_setter(v):
            call_count[0] += 1
            if call_count[0] > 3:  # Fail after 3 successful volume changes
                raise Exception("Speaker disconnected")

        type(mock_speaker).volume = PropertyMock(fget=volume_getter, fset=volume_setter)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                with pytest.raises(HTTPException) as exc_info:
                    await sonos_service.fade_speaker_volume("192.168.1.100", 100)

                assert exc_info.value.status_code == 503
                assert "Cannot connect to speaker" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fade_concurrent_operations_blocked(self, mock_speaker):
        """CRITICAL: Test concurrent operations on same speaker are blocked."""
        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.1):  # Slow fade
                # Start first fade (don't await yet)
                fade1_task = asyncio.create_task(
                    sonos_service.fade_speaker_volume("192.168.1.100", 100)
                )

                # Give first fade time to acquire lock
                await asyncio.sleep(0.05)

                # Try to start second fade on same speaker - should fail immediately
                with pytest.raises(HTTPException) as exc_info:
                    await sonos_service.fade_speaker_volume("192.168.1.100", 50)

                assert exc_info.value.status_code == 409
                assert exc_info.value.detail["error_code"] == ErrorCode.CONCURRENT_OPERATION.value

                # Wait for first fade to complete
                await fade1_task

    @pytest.mark.asyncio
    async def test_fade_different_speakers_concurrent(self, mock_multiple_speakers):
        """Test concurrent fades on different speakers work correctly."""

        def create_speaker_mock(initial_vol):
            mock = Mock()
            type(mock).volume = PropertyMock(return_value=initial_vol)
            mock.get_current_transport_info = Mock(
                return_value={"current_transport_state": "PLAYING"}
            )
            return mock

        speaker1 = create_speaker_mock(0)
        speaker2 = create_speaker_mock(0)

        def soco_factory(ip):
            return speaker1 if ip == "192.168.1.100" else speaker2

        with patch("app.services.sonos_service.SoCo", side_effect=soco_factory):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # Start fades on different speakers concurrently
                results = await asyncio.gather(
                    sonos_service.fade_speaker_volume("192.168.1.100", 80),
                    sonos_service.fade_speaker_volume("192.168.1.101", 60),
                )

                assert results[0]["ip"] == "192.168.1.100"
                assert results[0]["volume"] == 80
                assert results[1]["ip"] == "192.168.1.101"
                assert results[1]["volume"] == 60

    @pytest.mark.asyncio
    async def test_fade_volume_bounds_enforcement(self):
        """Test that volume stays within 0-100 bounds during fade."""
        volumes_set = []

        class MockSpeakerWithTracking:
            def __init__(self):
                self._volume = 0
                self.ip_address = "192.168.1.100"

            @property
            def volume(self):
                return self._volume

            @volume.setter
            def volume(self, v):
                self._volume = v
                volumes_set.append(v)

        mock_speaker = MockSpeakerWithTracking()

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                await sonos_service.fade_speaker_volume("192.168.1.100", 100)

                # All volumes should be within bounds
                assert all(0 <= v <= 100 for v in volumes_set)


class TestPlayUri:
    """Test playing audio from URI."""

    @pytest.mark.asyncio
    async def test_play_uri_success(self, mock_speaker):
        """Test successful URI playback."""
        test_uri = "http://example.com/audio.mp3"

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.play_uri("192.168.1.100", test_uri)

            assert result["ip"] == "192.168.1.100"
            assert result["uri"] == test_uri
            assert "Playing audio" in result["message"]

            # Verify speaker methods were called
            mock_speaker.clear_queue.assert_called_once()
            mock_speaker.play_uri.assert_called_once_with(test_uri)

    @pytest.mark.asyncio
    async def test_play_uri_clears_queue(self, mock_speaker):
        """Test that play_uri clears the queue before playing."""
        test_uri = "http://example.com/audio.mp3"

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            await sonos_service.play_uri("192.168.1.100", test_uri)

            # Verify queue was cleared
            mock_speaker.clear_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_play_uri_unreachable_speaker(self):
        """Test play_uri when speaker is unreachable."""
        mock_speaker = Mock()
        mock_speaker.clear_queue = Mock(side_effect=Exception("Connection timeout"))

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.play_uri("192.168.1.100", "http://test.mp3")

            assert exc_info.value.status_code == 503


class TestPauseSpeaker:
    """Test pausing speaker playback."""

    @pytest.mark.asyncio
    async def test_pause_speaker_success(self, mock_speaker):
        """Test successful speaker pause."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.pause_speaker("192.168.1.100")

            assert result["ip"] == "192.168.1.100"
            assert "Playback paused" in result["message"]
            mock_speaker.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_speaker_unreachable(self):
        """Test pause when speaker is unreachable."""
        mock_speaker = Mock()
        mock_speaker.pause = Mock(side_effect=Exception("Connection timeout"))

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.pause_speaker("192.168.1.100")

            assert exc_info.value.status_code == 503


class TestStopSpeaker:
    """Test stopping speaker playback."""

    @pytest.mark.asyncio
    async def test_stop_speaker_success(self, mock_speaker):
        """Test successful speaker stop."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            result = await sonos_service.stop_speaker("192.168.1.100")

            assert result["ip"] == "192.168.1.100"
            assert "Playback stopped" in result["message"]
            mock_speaker.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_speaker_unreachable(self):
        """Test stop when speaker is unreachable."""
        mock_speaker = Mock()
        mock_speaker.stop = Mock(side_effect=Exception("Connection timeout"))

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with pytest.raises(HTTPException) as exc_info:
                await sonos_service.stop_speaker("192.168.1.100")

            assert exc_info.value.status_code == 503


class TestConcurrentOperations:
    """Test concurrent operations and race conditions."""

    @pytest.mark.asyncio
    async def test_multiple_reads_concurrent(self, mock_speaker):
        """Test multiple concurrent status reads are allowed."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            # Multiple status checks should work concurrently
            results = await asyncio.gather(
                sonos_service.get_speaker_status("192.168.1.100"),
                sonos_service.get_speaker_status("192.168.1.100"),
                sonos_service.get_speaker_status("192.168.1.100"),
            )

            assert len(results) == 3
            assert all(r["ip"] == "192.168.1.100" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_instant_volume_changes(self, mock_speaker):
        """Test concurrent instant volume changes (no lock needed)."""
        type(mock_speaker).volume = PropertyMock(return_value=50)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            # Instant volume changes should work concurrently
            results = await asyncio.gather(
                sonos_service.set_speaker_volume("192.168.1.100", 30),
                sonos_service.set_speaker_volume("192.168.1.100", 60),
            )

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_fade_blocks_another_fade_same_speaker(self, mock_speaker):
        """Test that fade blocks another fade on the same speaker."""
        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.1):
                # Start first fade
                fade_task = asyncio.create_task(
                    sonos_service.fade_speaker_volume("192.168.1.100", 100)
                )

                # Give it time to acquire lock
                await asyncio.sleep(0.05)

                # Second fade should be blocked
                with pytest.raises(HTTPException) as exc_info:
                    await sonos_service.fade_speaker_volume("192.168.1.100", 50)

                assert exc_info.value.status_code == 409

                # Complete first fade
                await fade_task

    @pytest.mark.asyncio
    async def test_sequential_fades_after_completion(self, mock_speaker):
        """Test that sequential fades work after previous completes."""
        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # First fade
                result1 = await sonos_service.fade_speaker_volume("192.168.1.100", 50)
                assert result1["volume"] == 50

                # Second fade (should work since first is complete)
                result2 = await sonos_service.fade_speaker_volume("192.168.1.100", 80)
                assert result2["volume"] == 80


class TestAsyncWrappers:
    """Test that async wrappers work correctly."""

    @pytest.mark.asyncio
    async def test_run_in_thread_wraps_blocking_calls(self, mock_speaker):
        """Test that blocking soco calls are properly wrapped."""
        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            # All these operations should complete without blocking
            status = await sonos_service.get_speaker_status("192.168.1.100")
            assert status["ip"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_operations_dont_block_event_loop(self, mock_speaker):
        """Test that operations don't block the event loop."""
        type(mock_speaker).volume = PropertyMock(return_value=50)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            # Start multiple operations concurrently
            start_time = asyncio.get_event_loop().time()

            await asyncio.gather(
                sonos_service.get_speaker_status("192.168.1.100"),
                sonos_service.set_speaker_volume("192.168.1.100", 60),
                sonos_service.get_speaker_status("192.168.1.100"),
            )

            # Should complete quickly (not blocked)
            elapsed = asyncio.get_event_loop().time() - start_time
            assert elapsed < 1.0  # Should be much faster if properly async


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_fade_small_volume_change(self, mock_speaker):
        """Test fade with very small volume change uses minimum steps."""
        type(mock_speaker).volume = PropertyMock(return_value=50)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # Small change (1 volume unit)
                result = await sonos_service.fade_speaker_volume("192.168.1.100", 51)

                # Should use minimum steps for smoothness
                assert result["steps"] >= sonos_service.FADE_STEPS

    @pytest.mark.asyncio
    async def test_fade_large_volume_change(self, mock_speaker):
        """Test fade with large volume change."""
        type(mock_speaker).volume = PropertyMock(return_value=0)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # Large change (0 to 100)
                result = await sonos_service.fade_speaker_volume("192.168.1.100", 100)

                # Should use more steps for large change
                assert result["steps"] >= 100

    @pytest.mark.asyncio
    async def test_discovery_with_coordinator_and_follower(self, mock_multiple_speakers):
        """Test discovery with both coordinator and follower speakers."""
        mock_multiple_speakers[1].is_coordinator = False  # Make second speaker a follower

        with patch("soco.discover", return_value=iter(mock_multiple_speakers)):
            speakers = await sonos_service.discover_speakers()

            # Should discover both coordinator and follower
            assert len(speakers) == 3
            coordinators = [s for s in speakers if s["is_coordinator"]]
            followers = [s for s in speakers if not s["is_coordinator"]]

            assert len(coordinators) == 2
            assert len(followers) == 1

    @pytest.mark.asyncio
    async def test_empty_track_info(self, mock_speaker):
        """Test status with empty/missing track info."""
        mock_speaker.get_current_track_info.return_value = {}

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            status = await sonos_service.get_speaker_status("192.168.1.100")

            assert status["current_track"]["title"] == ""
            assert status["current_track"]["artist"] == ""
            assert status["current_track"]["album"] == ""

    @pytest.mark.asyncio
    async def test_fade_lock_cleanup_after_error(self, mock_speaker):
        """Test that speaker lock is properly released after error."""
        call_count = [0]

        def volume_getter_setter(v=None):
            if v is None:
                return 0
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on second call
                raise Exception("Connection lost")

        type(mock_speaker).volume = PropertyMock(side_effect=volume_getter_setter)

        with patch("app.services.sonos_service.SoCo", return_value=mock_speaker):
            with patch("app.services.sonos_service.FADE_BASE_SLEEP", new=0.01):
                # First fade should fail
                with pytest.raises(HTTPException):
                    await sonos_service.fade_speaker_volume("192.168.1.100", 100)

                # Reset mock
                call_count[0] = 0
                type(mock_speaker).volume = PropertyMock(return_value=0)

                # Second fade should work (lock was released)
                result = await sonos_service.fade_speaker_volume("192.168.1.100", 50)
                assert result["volume"] == 50
