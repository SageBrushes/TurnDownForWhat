# Turn Down For What - Enhanced Sonos Volume Controller

A Python script that discovers Sonos speakers on your network and gradually adjusts their volume to a target level using smooth fade curves and comprehensive logging.

## Features

- **Speaker Discovery**: Automatically finds all Sonos speakers on your local network
- **Smart Volume Adjustment**: Uses smooth S-curve fading instead of harsh linear steps
- **Speaker Status Display**: Shows current playback state (🎵 playing, ⏸️ paused, ⏹️ stopped) and track information
- **Comprehensive Logging**: Timestamped logs with progress indicators and execution time tracking
- **Error Handling**: Graceful handling of network issues and keyboard interrupts
- **Skip Logic**: Automatically skips speakers already at target volume

## Prerequisites

- **Python 3.6 or higher**: Required for f-string support and compatibility
- **Sonos Speakers**: At least one Sonos speaker connected to your network
- **Same Network**: Device running the script must be on the same network as Sonos speakers

## Installation

### Clone the Repository

```bash
git clone https://github.com/sagebrushes/TurnDownForWhat.git
cd TurnDownForWhat
```

### Set Up Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install soco
```

## Usage

### Basic Usage

```bash
# With virtual environment activated
python turndownmusic.py

# Or directly (if dependencies are installed globally)
python3 turndownmusic.py
```

### What the Script Does

1. **Discovery Phase**: Scans your network for Sonos speakers
2. **Status Display**: Shows each speaker's current volume, playback status, and current track
3. **Volume Adjustment**: Gradually fades each speaker's volume to the target level (default: 5)
4. **Progress Tracking**: Displays real-time progress and completion status

### Sample Output

```
[14:32:15] ===== Sonos Volume Adjuster Starting =====
[14:32:15] Discovering Sonos speakers on your network...
[14:32:16] ✓ Network scan complete
[14:32:16] Found 3 Sonos speakers on your network:
[14:32:16] 1. Living Room (IP: 192.168.1.100)
[14:32:16]    Status: 🎵 Playing
[14:32:16]    Current volume: 25
[14:32:16]    Playing: Your Favorite Song
[14:32:16] Starting volume adjustment process to target volume: 5

[14:32:16] Processing speaker 1/3: Living Room
[14:32:16] Fading volume down for Living Room (smooth curve)...
[14:32:18] ✓ Living Room volume adjustment complete: 5
[14:32:18] ===== Process Complete =====
[14:32:18] ✓ All 3 speakers adjusted to volume level 5
[14:32:18] Total execution time: 2.3 seconds
```

## Advanced Features

### Smooth Volume Curves

The script uses mathematical S-curves (sine-based) for natural-sounding volume transitions:
- **Ease-in-out**: Starts slow, accelerates in middle, slows at end
- **Variable timing**: Faster steps in middle, slower at start/end
- **Minimum steps**: At least 10 steps regardless of volume difference for smoothness

### Error Handling

- **Network issues**: Graceful handling of speaker connectivity problems
- **Keyboard interrupts**: Clean exit with Ctrl+C
- **Speaker errors**: Individual speaker failures don't stop the process
- **Bounds checking**: Volume values automatically clamped to 0-100 range

## Troubleshooting

### No Speakers Found

- Ensure Sonos speakers are powered on and connected to your network
- Verify you're on the same network as your Sonos speakers
- Check that no firewall is blocking network discovery

### Virtual Environment Issues

On macOS with Homebrew Python, you may need a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install soco
python turndownmusic.py
```

### Permission Errors

If you get externally-managed-environment errors:

```bash
# Use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install soco

# Or use pipx for isolated installation
pipx run --spec soco python turndownmusic.py
```

## Customization

The script can be easily modified to:
- Change target volume (currently hardcoded to 5)
- Adjust fade curve parameters
- Modify timing intervals
- Add command-line arguments

## Contributing

Contributions are welcome! Please submit a pull request or open an issue to discuss changes.

## Acknowledgments

- **[SoCo Library](https://github.com/SoCo/SoCo)**: For providing the tools to interact with Sonos speakers
- **Community**: For ideas and feedback on improving the script