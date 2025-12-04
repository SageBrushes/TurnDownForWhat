from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import soco
import threading
import time
import math

app = Flask(__name__)
CORS(app)

# Store current operation status
operation_status = {
    'running': False,
    'progress': [],
    'error': None
}

def get_speakers():
    """Discover and return all Sonos speakers with their current status"""
    try:
        speakers = list(soco.discover())
        if not speakers:
            return []

        speaker_list = []
        for speaker in speakers:
            try:
                transport_info = speaker.get_current_transport_info()
                playback_state = transport_info['current_transport_state']
                current_track_info = speaker.get_current_track_info()
                track_title = current_track_info.get('title', 'No media')

                speaker_data = {
                    'name': speaker.player_name,
                    'ip': speaker.ip_address,
                    'volume': speaker.volume,
                    'state': playback_state,
                    'track': track_title
                }
                speaker_list.append(speaker_data)
            except Exception as e:
                speaker_data = {
                    'name': speaker.player_name,
                    'ip': speaker.ip_address,
                    'volume': speaker.volume,
                    'state': 'UNKNOWN',
                    'track': 'Error getting info',
                    'error': str(e)
                }
                speaker_list.append(speaker_data)

        return speaker_list
    except Exception as e:
        return {'error': str(e)}

def adjust_volume_background(target_volume):
    """Background task to adjust volumes"""
    global operation_status
    operation_status['running'] = True
    operation_status['progress'] = []
    operation_status['error'] = None

    try:
        speakers = list(soco.discover())
        if not speakers:
            operation_status['error'] = 'No speakers found'
            operation_status['running'] = False
            return

        operation_status['progress'].append(f"Found {len(speakers)} speakers")

        for i, speaker in enumerate(speakers, 1):
            current_volume = speaker.volume
            operation_status['progress'].append(
                f"Processing {speaker.player_name}: {current_volume} → {target_volume}"
            )

            if current_volume == target_volume:
                operation_status['progress'].append(
                    f"{speaker.player_name} already at target volume"
                )
                continue

            # Use smooth fade curve
            volume_difference = abs(target_volume - current_volume)
            steps = max(volume_difference, 10)
            fade_direction = "up" if current_volume < target_volume else "down"

            for step in range(steps + 1):
                progress = step / steps

                if fade_direction == "up":
                    smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
                    vol = int(current_volume + (target_volume - current_volume) * smooth_progress)
                else:
                    smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
                    vol = int(current_volume - (current_volume - target_volume) * smooth_progress)

                vol = max(0, min(100, vol))
                speaker.volume = vol

                sleep_factor = 1.0 - 0.5 * math.sin(math.pi * progress)
                time.sleep(0.3 * sleep_factor)

            operation_status['progress'].append(
                f"✓ {speaker.player_name} complete: {target_volume}"
            )

        operation_status['progress'].append(
            f"All {len(speakers)} speakers adjusted to volume {target_volume}"
        )

    except Exception as e:
        operation_status['error'] = str(e)
    finally:
        operation_status['running'] = False

@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')

@app.route('/api/speakers', methods=['GET'])
def api_speakers():
    """Get all speakers and their current status"""
    speakers = get_speakers()
    return jsonify(speakers)

@app.route('/api/adjust', methods=['POST'])
def api_adjust():
    """Start volume adjustment for all speakers"""
    data = request.get_json()
    target_volume = data.get('target_volume', 5)

    if not 0 <= target_volume <= 100:
        return jsonify({'error': 'Volume must be between 0 and 100'}), 400

    if operation_status['running']:
        return jsonify({'error': 'Operation already in progress'}), 409

    # Start adjustment in background thread
    thread = threading.Thread(target=adjust_volume_background, args=(target_volume,))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'target_volume': target_volume})

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get current operation status"""
    return jsonify(operation_status)

@app.route('/api/speaker/<speaker_name>/volume', methods=['POST'])
def api_set_speaker_volume(speaker_name):
    """Set volume for a specific speaker"""
    data = request.get_json()
    target_volume = data.get('volume')

    if target_volume is None or not 0 <= target_volume <= 100:
        return jsonify({'error': 'Volume must be between 0 and 100'}), 400

    try:
        speakers = list(soco.discover())
        for speaker in speakers:
            if speaker.player_name == speaker_name:
                speaker.volume = target_volume
                return jsonify({'status': 'success', 'volume': target_volume})

        return jsonify({'error': 'Speaker not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
