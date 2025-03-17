import soco
import time

def slowly_adjust_volume(speakers, target_volume=5):
    # Find all Sonos speakers
    print(f"Found {len(speakers)} Sonos speakers on your network:")
    for i, speaker in enumerate(speakers):
        print(f"{i+1}. {speaker.player_name} (Current volume: {speaker.volume})")
    
    # Slowly adjust volume for each speaker
    for speaker in speakers:
        current_volume = speaker.volume
        print(f"\nAdjusting volume for {speaker.player_name}...")
        
        # Determine if we need to increase or decrease volume
        if current_volume < target_volume:
            # Volume up
            for vol in range(current_volume, target_volume + 1):
                speaker.volume = vol
                print(f"  Volume: {vol}", end="\r")
                time.sleep(0.5)
        else:
            # Volume down
            for vol in range(current_volume, target_volume - 1, -1):
                speaker.volume = vol
                print(f"  Volume: {vol}", end="\r")
                time.sleep(0.5)
        
        print(f"\n{speaker.player_name} volume set to {target_volume}   ")

def main():
    try:
        # Discover all Sonos speakers on the network
        print("Discovering Sonos speakers on your network...")
        speakers = list(soco.discover())
        
        if not speakers:
            print("No Sonos speakers found on your network.")
            return
            
        # Adjust volume to 5 for all speakers
        slowly_adjust_volume(speakers, 5)
        
        print("\nAll speakers adjusted to volume level 5")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
