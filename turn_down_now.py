#!/usr/bin/env python3
"""Quick script to turn down music on all Sonos speakers."""
import asyncio
import sys
from pathlib import Path

# Add the app directory to the path so we can import the service
sys.path.insert(0, str(Path(__file__).parent))

from app.services.sonos_service import discover_speakers, set_speaker_volume


async def turn_down_music(target_volume: int = 10):
    """
    Turn down all Sonos speakers to the target volume.

    Args:
        target_volume: Target volume level (0-100), default is 10
    """
    print(f"🔊 Turning down music to volume {target_volume}...")
    print("🔍 Discovering Sonos speakers on your network...")

    try:
        # Discover all speakers
        speakers = await discover_speakers(force_refresh=True)

        if not speakers:
            print("❌ No Sonos speakers found on the network")
            return

        print(f"✅ Found {len(speakers)} speaker(s):")
        for speaker in speakers:
            print(f"   • {speaker['name']} (current volume: {speaker['volume']})")

        print(f"\n🎚️  Setting all speakers to volume {target_volume}...")

        # Set volume on each speaker
        success_count = 0
        for speaker in speakers:
            try:
                await set_speaker_volume(speaker["ip"], target_volume)
                print(f"   ✓ {speaker['name']}: {speaker['volume']} → {target_volume}")
                success_count += 1
            except Exception as e:
                print(f"   ✗ {speaker['name']}: Failed - {e}")

        print(f"\n🎉 Done! Successfully adjusted {success_count}/{len(speakers)} speaker(s)")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Allow volume to be passed as command line argument
    target_volume = 10
    if len(sys.argv) > 1:
        try:
            target_volume = int(sys.argv[1])
            if not 0 <= target_volume <= 100:
                print("❌ Volume must be between 0 and 100")
                sys.exit(1)
        except ValueError:
            print("❌ Invalid volume. Please provide a number between 0 and 100")
            sys.exit(1)

    # Run the async function
    asyncio.run(turn_down_music(target_volume))
