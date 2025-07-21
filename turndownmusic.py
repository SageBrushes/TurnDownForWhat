import soco
import time
import datetime
import math

def slowly_adjust_volume(speakers, target_volume=5):
    # Find all Sonos speakers
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Found {len(speakers)} Sonos speakers on your network:")
    for i, speaker in enumerate(speakers):
        try:
            transport_info = speaker.get_current_transport_info()
            playback_state = transport_info['current_transport_state']
            status_emoji = "🎵" if playback_state == "PLAYING" else "⏸️" if playback_state == "PAUSED_PLAYBACK" else "⏹️"
            
            current_track_info = speaker.get_current_track_info()
            track_title = current_track_info.get('title', 'No media')
            
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {i+1}. {speaker.player_name} (IP: {speaker.ip_address})")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]    Status: {status_emoji} {playback_state.replace('_', ' ').title()}")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]    Current volume: {speaker.volume}")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]    Playing: {track_title}")
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {i+1}. {speaker.player_name} (IP: {speaker.ip_address}, Current volume: {speaker.volume})")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]    Status: ❓ Unknown (error: {e})")
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Starting volume adjustment process to target volume: {target_volume}")
    
    # Slowly adjust volume for each speaker
    for i, speaker in enumerate(speakers, 1):
        current_volume = speaker.volume
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Processing speaker {i}/{len(speakers)}: {speaker.player_name}")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Current volume: {current_volume} -> Target volume: {target_volume}")
        
        if current_volume == target_volume:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {speaker.player_name} already at target volume {target_volume}, skipping...")
            continue
            
        # Use smooth fade curve instead of linear steps
        volume_difference = abs(target_volume - current_volume)
        steps = max(volume_difference, 10)  # Minimum 10 steps for smoothness
        
        if current_volume < target_volume:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Fading volume up for {speaker.player_name} (smooth curve)...")
            fade_direction = "up"
        else:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Fading volume down for {speaker.player_name} (smooth curve)...")
            fade_direction = "down"
            
        for step in range(steps + 1):
            # Use smooth S-curve (sigmoid-like) for natural fade
            progress = step / steps
            
            if fade_direction == "up":
                # Ease-in-out curve for volume increase
                smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
                vol = int(current_volume + (target_volume - current_volume) * smooth_progress)
            else:
                # Ease-in-out curve for volume decrease  
                smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
                vol = int(current_volume - (current_volume - target_volume) * smooth_progress)
            
            # Ensure volume stays within bounds
            vol = max(0, min(100, vol))
            
            speaker.volume = vol
            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] Volume: {vol} (step {step+1}/{steps+1})", end="\r")
            
            # Variable sleep time - faster in middle, slower at start/end for smoother feel
            sleep_factor = 1.0 - 0.5 * math.sin(math.pi * progress)
            time.sleep(0.3 * sleep_factor)
        
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] ✓ {speaker.player_name} volume adjustment complete: {target_volume}")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Remaining speakers: {len(speakers) - i}")

def main():
    start_time = datetime.datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S')}] ===== Sonos Volume Adjuster Starting =====")
    
    try:
        # Discover all Sonos speakers on the network
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Discovering Sonos speakers on your network...")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Scanning local network for Sonos devices...")
        
        speakers = list(soco.discover())
        
        if not speakers:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ❌ No Sonos speakers found on your network.")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Please ensure:")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]   - Sonos speakers are powered on")
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]   - You're connected to the same network as your Sonos speakers")
            return
            
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✓ Network scan complete")
        
        # Adjust volume to 5 for all speakers
        slowly_adjust_volume(speakers, 5)
        
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        print(f"\n[{end_time.strftime('%H:%M:%S')}] ===== Process Complete =====")
        print(f"[{end_time.strftime('%H:%M:%S')}] ✓ All {len(speakers)} speakers adjusted to volume level 5")
        print(f"[{end_time.strftime('%H:%M:%S')}] Total execution time: {duration.total_seconds():.1f} seconds")
        
    except KeyboardInterrupt:
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚠️ Process interrupted by user")
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ❌ An error occurred: {e}")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()
