#!/usr/bin/env python3
"""Quick script to turn down music on all Sonos speakers - Direct approach."""
import soco
import time
import sys


def turn_down_music(target_volume: int = 10):
    """
    Turn down all Sonos speakers to the target volume.

    Args:
        target_volume: Target volume level (0-100), default is 10
    """
    print(f"🔊 Turning down music to volume {target_volume}...")
    print("🔍 Discovering Sonos speakers on your network...")

    try:
        # Try direct discovery with timeout
        speakers = list(soco.discover(timeout=10))

        if not speakers:
            print("❌ No Sonos speakers found on the network")
            print("   Make sure:")
            print("   • Sonos speakers are powered on")
            print("   • You're on the same network as your Sonos speakers")
            print("   • No firewall is blocking network discovery")
            return

        print(f"✅ Found {len(speakers)} speaker(s):")
        for speaker in speakers:
            try:
                print(f"   • {speaker.player_name} (current volume: {speaker.volume})")
            except Exception as e:
                print(f"   • {speaker.ip_address} (couldn't get details: {e})")

        print(f"\n🎚️  Setting all speakers to volume {target_volume}...")

        # Set volume on each speaker
        success_count = 0
        for speaker in speakers:
            try:
                old_volume = speaker.volume
                speaker.volume = target_volume
                print(f"   ✓ {speaker.player_name}: {old_volume} → {target_volume}")
                success_count += 1
                time.sleep(0.1)  # Small delay between operations
            except Exception as e:
                print(f"   ✗ {speaker.ip_address}: Failed - {e}")

        print(f"\n🎉 Done! Successfully adjusted {success_count}/{len(speakers)} speaker(s)")

    except Exception as e:
        print(f"❌ Error during discovery: {e}")
        print("\nTroubleshooting:")
        print("1. Check that you're on the same WiFi network as your Sonos speakers")
        print("2. Try running: ping <speaker-ip> to verify network connectivity")
        print("3. Make sure no VPN is active that might block multicast")
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

    turn_down_music(target_volume)
