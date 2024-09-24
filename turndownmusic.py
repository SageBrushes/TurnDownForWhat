import sys
import soco
import logging
from xml.etree import ElementTree as ET

# Ensure Python version compatibility
if sys.version_info < (3, 6):
    sys.exit("This script requires Python 3.6 or higher.")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Constants
MAX_VOLUME = 15

def main():
    """
    Main function to discover Sonos speakers and perform actions.
    """
    try:
        speakers = soco.discover()
        if not speakers:
            logging.info("No Sonos speakers found on the network.")
            return

        for speaker in speakers:
            display_speaker_info(speaker)
            display_current_track(speaker)
            adjust_volume_if_needed(speaker, max_volume=MAX_VOLUME)
    except KeyboardInterrupt:
        logging.info("\nScript interrupted by user.")
    except soco.exceptions.SoCoException as e:
        logging.error(f"An error occurred: {e}")

def display_speaker_info(speaker):
    """
    Displays information about the speaker.

    Args:
        speaker (SoCo): The SoCo speaker instance.
    """
    logging.info(f"Speaker: {speaker.player_name}")
    logging.info(f"  IP Address: {speaker.ip_address}")
    try:
        speaker_info = speaker.get_speaker_info()
        logging.info(f"  Model: {speaker_info.get('model_name', 'Unknown Model')}")
        logging.info(f"  Software Version: {speaker_info.get('software_version', 'Unknown Version')}")
        logging.info(f"  Room Name: {speaker_info.get('zone_name', 'Unknown Room')}")
        logging.info(f"  MAC Address: {speaker_info.get('mac_address', 'Unknown MAC')}")
        logging.info(f"  Is Coordinator: {'Yes' if speaker.is_coordinator else 'No'}")
        logging.info(f"  Mute Status: {'Muted' if speaker.mute else 'Unmuted'}")
        logging.info(f"  Bass Level: {speaker.bass}")
        logging.info(f"  Treble Level: {speaker.treble}")
        logging.info(f"  Loudness: {'On' if speaker.loudness else 'Off'}")
    except soco.exceptions.SoCoException as e:
        logging.error(f"  Error getting speaker info: {e}")

def display_current_track(speaker):
    """
    Displays current track information of the speaker, including the music service.

    Args:
        speaker (SoCo): The SoCo speaker instance.
    """
    try:
        track_info = speaker.get_current_track_info()
        title = track_info.get('title', '').strip()
        artist = track_info.get('artist', '').strip()
        album = track_info.get('album', '').strip()
        uri = track_info.get('uri', '').strip()

        if title or artist:
            logging.info(f"  Now Playing: {title} - {artist}")
        else:
            logging.info("  Now Playing: Nothing")

        # Get the music service information
        transport_info = speaker.avTransport.GetMediaInfo([
            ('InstanceID', 0)
        ])

        current_uri = transport_info.get('CurrentURI', '')
        current_uri_metadata = transport_info.get('CurrentURIMetaData', '')

        service_name = 'Unknown Service'

        if 'x-sonosapi-stream:' in current_uri:
            service_name = 'Radio Stream'
        elif 'spotify' in current_uri.lower():
            service_name = 'Spotify'
        elif 'apple.com' in current_uri.lower():
            service_name = 'Apple Music'
        elif 'soundcloud' in current_uri.lower():
            service_name = 'SoundCloud'
        elif 'pandora' in current_uri.lower():
            service_name = 'Pandora'
        elif 'amz' in current_uri.lower() or 'amazon' in current_uri.lower():
            service_name = 'Amazon Music'
        elif 'file:' in current_uri.lower():
            service_name = 'Local Music Library'
        else:
            # Try to parse the metadata for the service name
            if current_uri_metadata:
                try:
                    didl = ET.fromstring(current_uri_metadata)
                    service_element = didl.find('.//{urn:schemas-rinconnetworks-com:metadata-1-0/}streamContent')
                    if service_element is not None and service_element.text:
                        service_name = service_element.text.strip()
                except ET.ParseError:
                    pass

        logging.info(f"  Music Service: {service_name}")

        # Display playback state
        transport_state = speaker.get_current_transport_info().get('current_transport_state', 'UNKNOWN')
        logging.info(f"  Playback State: {transport_state}")

        # Display play mode settings
        play_mode = speaker.play_mode
        logging.info(f"  Play Mode: {play_mode}")

        # Display crossfade status
        crossfade = speaker.cross_fade
        logging.info(f"  Crossfade: {'On' if crossfade else 'Off'}")

        # Display queue length
        queue = speaker.get_queue(max_items=0)
        queue_length = queue.total_matches
        logging.info(f"  Queue Length: {queue_length}")

    except soco.exceptions.SoCoException as e:
        logging.error(f"  Error getting track info: {e}")

def adjust_volume_if_needed(speaker, max_volume):
    """
    Adjusts the speaker's volume if it exceeds the maximum allowed volume.

    Args:
        speaker (SoCo): The SoCo speaker instance.
        max_volume (int): The maximum allowed volume level.
    """
    try:
        volume = speaker.volume
        logging.info(f"  Volume: {volume}")
        if volume > max_volume:
            speaker.volume = max_volume
            logging.info(f"  Volume adjusted to {max_volume} due to being over the limit.")
    except soco.exceptions.SoCoException as e:
        logging.error(f"  Error getting or setting volume: {e}")

if __name__ == "__main__":
    main()

