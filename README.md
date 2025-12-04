# Turn Down For What - Sonos Volume Controller Web App

A modern web application for discovering and controlling Sonos speakers on your network. Features smooth volume adjustments, real-time speaker status, and an intuitive web interface.

## Features

### Web Interface
- **Modern, Responsive UI**: Beautiful gradient design that works on desktop and mobile
- **Real-Time Speaker Cards**: Visual display of all speakers with current status
- **Individual Volume Control**: Adjust each speaker independently with sliders
- **Batch Adjustment**: Set all speakers to a target volume at once
- **Live Activity Log**: See all operations in real-time
- **Auto-Refresh**: Keep speaker status up-to-date

### Sonos Integration
- **Automatic Discovery**: Finds all Sonos speakers on your local network
- **Smart Volume Adjustment**: Uses smooth S-curve fading for natural transitions
- **Playback Status**: Shows current state (🎵 playing, ⏸️ paused, ⏹️ stopped) and track info
- **RESTful API**: JSON API for integration with other tools
- **Error Handling**: Graceful handling of network issues and speaker errors

## Prerequisites

- **Python 3.11 or higher**: Required for running the web application
- **Sonos Speakers**: At least one Sonos speaker connected to your network
- **Same Network**: Server must be on the same network as Sonos speakers
- **Docker** (optional): For containerized deployment

## Installation & Deployment

### Method 1: Using the Run Script (Recommended)

```bash
# Clone the repository
git clone https://github.com/sagebrushes/TurnDownForWhat.git
cd TurnDownForWhat

# Run the startup script
./run.sh
```

The app will be available at `http://localhost:5000`

### Method 2: Docker Deployment

```bash
# Using Docker Compose
docker-compose up -d

# Or using Docker directly
docker build -t turndownforwhat .
docker run -p 5000:5000 --network host turndownforwhat
```

**Note**: The `--network host` flag is required for Sonos speaker discovery on the local network.

### Method 3: Manual Installation

```bash
# Clone the repository
git clone https://github.com/sagebrushes/TurnDownForWhat.git
cd TurnDownForWhat

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run with Flask development server (development only)
python app.py

# Or run with Gunicorn (production)
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
```

## Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:5000` (or your server's address)
2. The app will automatically discover all Sonos speakers on your network
3. View real-time status of all speakers including:
   - Current volume level
   - Playback state
   - Currently playing track
4. **Individual Control**: Use the slider on each speaker card to adjust volume
5. **Batch Control**: Set a target volume and click "Adjust All Speakers" to fade all speakers together
6. Monitor progress in the Activity Log at the bottom

### Command Line (Legacy)

The original Python script is still available:

```bash
python turndownmusic.py
```

## API Documentation

The application provides a RESTful API for integration with other tools:

### Endpoints

#### `GET /api/speakers`
Returns list of all discovered speakers with current status.

**Response:**
```json
[
  {
    "name": "Living Room",
    "ip": "192.168.1.100",
    "volume": 25,
    "state": "PLAYING",
    "track": "Your Favorite Song"
  }
]
```

#### `POST /api/adjust`
Adjust all speakers to target volume.

**Request:**
```json
{
  "target_volume": 5
}
```

**Response:**
```json
{
  "status": "started",
  "target_volume": 5
}
```

#### `POST /api/speaker/{name}/volume`
Set volume for a specific speaker.

**Request:**
```json
{
  "volume": 15
}
```

**Response:**
```json
{
  "status": "success",
  "volume": 15
}
```

#### `GET /api/status`
Get current operation status.

**Response:**
```json
{
  "running": true,
  "progress": ["Found 3 speakers", "Processing Living Room..."],
  "error": null
}
```

## Advanced Features

### Smooth Volume Curves

The application uses mathematical S-curves (sine-based) for natural-sounding volume transitions:
- **Ease-in-out**: Starts slow, accelerates in middle, slows at end
- **Variable timing**: Faster steps in middle, slower at start/end
- **Minimum steps**: At least 10 steps regardless of volume difference for smoothness

### Error Handling

- **Network issues**: Graceful handling of speaker connectivity problems
- **Speaker errors**: Individual speaker failures don't stop the process
- **Bounds checking**: Volume values automatically clamped to 0-100 range
- **Concurrent operations**: Prevents multiple simultaneous adjustments

## Deployment to donni.org

### Prerequisites for Production
- Server with network access to Sonos speakers
- Domain configured to point to your server (e.g., donni.org)
- Reverse proxy (nginx/Apache) for HTTPS support

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name donni.org;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd Service (for production)

Create `/etc/systemd/system/turndownforwhat.service`:

```ini
[Unit]
Description=Turn Down For What Sonos Controller
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/TurnDownForWhat
Environment="PATH=/opt/TurnDownForWhat/venv/bin"
ExecStart=/opt/TurnDownForWhat/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl enable turndownforwhat
sudo systemctl start turndownforwhat
```

## Troubleshooting

### No Speakers Found

- Ensure Sonos speakers are powered on and connected to your network
- Verify the server is on the same network as your Sonos speakers
- Check that no firewall is blocking network discovery (UDP port 1900)
- If using Docker, ensure `--network host` is set

### Web Interface Not Loading

- Check that the server is running: `ps aux | grep gunicorn`
- Verify port 5000 is accessible: `netstat -tulpn | grep 5000`
- Check logs for errors

### Volume Adjustments Not Working

- Ensure speakers are not grouped (grouped speakers may behave differently)
- Check network connectivity between server and speakers
- Verify no other applications are controlling the speakers

## Customization

The application can be customized by modifying:

- **`app.py`**: Backend logic, API endpoints, adjustment algorithms
- **`templates/index.html`**: UI design, colors, layout
- **Target volumes**: Change default values in the frontend or backend
- **Fade curves**: Adjust the mathematical curve in the `adjust_volume_background` function
- **Timing**: Modify sleep intervals for faster/slower adjustments

## Contributing

Contributions are welcome! Please submit a pull request or open an issue to discuss changes.

## Acknowledgments

- **[SoCo Library](https://github.com/SoCo/SoCo)**: For providing the tools to interact with Sonos speakers
- **Community**: For ideas and feedback on improving the script