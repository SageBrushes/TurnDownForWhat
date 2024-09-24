
# Sonos Volume Monitor with Slack Notifications

This Python script monitors Sonos speakers on your network, adjusts their volume if it exceeds a specified maximum, and sends notifications to a Slack channel when the volume is adjusted. The script runs continuously and checks the speakers at regular intervals.

## Features

- **Volume Monitoring**: Continuously monitors the volume of Sonos speakers.
- **Automatic Adjustment**: Lowers the volume if it exceeds a defined maximum.
- **Slack Notifications**: Sends a message to a Slack channel when the volume is adjusted.
- **Debounce Mechanism**: Prevents spamming by ensuring notifications are sent no more than once every 5 minutes per speaker.
- **Group Handling**: Processes only coordinator speakers to avoid duplicate notifications in grouped speakers.
- **Logging**: Logs activities and errors to both the console and a log file.

## Prerequisites

- **Python 3.6 or higher**: Required for f-string support and compatibility.
- **Sonos Speakers**: At least one Sonos speaker connected to your network.
- **Slack Workspace**: Access to a Slack workspace where you can create a Slack app and receive notifications.
- **Raspberry Pi or Other Device**: A device to run the script continuously (e.g., Raspberry Pi).

## Installation

### Clone the Repository

Clone this repository to your local machine or directly onto your Raspberry Pi:

```bash
git clone https://github.com/yourusername/sonos-volume-monitor.git
```

Navigate to the project directory:

```bash
cd sonos-volume-monitor
```

### Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install soco slack_sdk python-dotenv
```

- **soco**: Library for controlling Sonos speakers.
- **slack_sdk**: Slack SDK for Python to interact with the Slack API.
- **python-dotenv**: To load environment variables from a `.env` file.

## Configuration

### 1. Set Up Slack App

#### Create a Slack App and Obtain a Bot Token

- **Create a Slack App**:
  - Go to [Slack API Apps](https://api.slack.com/apps) and click **"Create New App"**.
  - Choose **"From scratch"**, give your app a name (e.g., `SonosVolumeBot`), and select your workspace.

- **Configure App Permissions**:
  - Navigate to **"OAuth & Permissions"** in your app settings.
  - Under **"Scopes"**, add the following **Bot Token Scopes**:
    - `chat:write`
  - Click **"Install App to Workspace"** and authorize the app.
  - Copy the **Bot User OAuth Token** (starts with `xoxb-`).

- **Invite the Bot to Your Slack Channel**:
  - In Slack, invite your bot to the channel where you want to receive notifications using `/invite @SonosVolumeBot`.

#### Get Your Slack Channel ID

- Open Slack and navigate to the channel.
- Click on the channel name to view details.
- The URL will have the channel ID in the format `C01234567`.
- Alternatively, right-click on the channel name and select **"Copy Link"**.

### 2. Configure Environment Variables

Create a `.env` file in the project directory to securely store your Slack credentials:

```bash
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=your-slack-channel-id
```

- Replace `xoxb-your-slack-bot-token` with your actual Slack bot token.
- Replace `your-slack-channel-id` with the ID of the Slack channel.

### 3. Adjust Script Constants (Optional)

Open `turndownmusic.py` in a text editor and adjust the constants if necessary:

```python
MAX_VOLUME = 15          # Maximum allowed volume
CHECK_INTERVAL = 30      # Time in seconds between volume checks
DEBOUNCE_INTERVAL = 300  # Time in seconds between notifications per speaker
```

## Usage

### Running the Script

Run the script using Python 3:

```bash
python3 turndownmusic.py
```

- The script will continuously monitor your Sonos speakers.
- It adjusts the volume if it exceeds the `MAX_VOLUME`.
- Sends a Slack notification when the volume is adjusted, no more than once every `DEBOUNCE_INTERVAL` seconds per speaker.

### Running the Script in the Background

To keep the script running even after closing the terminal or logging out, run it in the background or as a service.

#### Using `nohup`

```bash
nohup python3 turndownmusic.py &
```

#### Using `screen`

```bash
screen -S sonos_monitor
python3 turndownmusic.py
```

Detach from the screen session with `Ctrl+A` then `D`.

#### Using `tmux`

```bash
tmux new -s sonos_monitor
python3 turndownmusic.py
```

Detach from the tmux session with `Ctrl+B` then `D`.

#### Using `systemd` Service

Create a systemd service file to run the script as a service on startup.

1. **Create Service File**

   ```bash
   sudo nano /etc/systemd/system/sonos_volume_monitor.service
   ```

2. **Add the Following Content**

   ```ini
   [Unit]
   Description=Sonos Volume Monitor Service
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /path/to/your/project/turndownmusic.py
   WorkingDirectory=/path/to/your/project
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```

   - Replace `/path/to/your/project` with the actual path to your script.
   - Ensure `User` is set to the correct user (e.g., `pi`).

3. **Reload systemd and Enable Service**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sonos_volume_monitor.service
   sudo systemctl start sonos_volume_monitor.service
   ```

4. **Check Service Status**

   ```bash
   sudo systemctl status sonos_volume_monitor.service
   ```

## Logging

The script logs its activities to both the console and a log file named `volume_monitor.log` in the project directory.

- **Log Format**: Includes timestamps, log levels, and messages.
- **Log Levels**: `INFO`, `ERROR`, etc.

### Viewing Logs

- **In Real-Time**:

  ```bash
  tail -f volume_monitor.log
  ```

- **Entire Log File**:

  ```bash
  cat volume_monitor.log
  ```

## Troubleshooting

### Slack Notifications Not Appearing

- **Ensure Bot Is Invited**: Use `/invite @SonosVolumeBot` in your Slack channel.
- **Check Permissions**: Verify that the bot has the `chat:write` scope.
- **Review Slack API Errors**: Errors are logged and can indicate permission issues.

### Script Not Discovering Speakers

- **Network Connection**: Ensure the device running the script is on the same network as your Sonos speakers.
- **Firewall Settings**: Check that no firewall is blocking the required ports.
- **Sonos System Updates**: Ensure your Sonos speakers are updated to the latest firmware.

### Multiple Notifications

- **Grouped Speakers**: The script processes only coordinator speakers to avoid duplicates.
- **Debounce Interval**: Adjust `DEBOUNCE_INTERVAL` if notifications are too frequent.

### Error Messages in Logs

- **Syntax Errors**: Ensure you are running the script with Python 3.6 or higher.
- **Dependency Issues**: Verify that all required packages are installed.
- **Environment Variables**: Check that the `.env` file is correctly configured.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue to discuss changes.

## License

This project is licensed under the MIT License.

## Acknowledgments

- **[SoCo Library](https://github.com/SoCo/SoCo)**: For providing the tools to interact with Sonos speakers.
- **[Slack SDK for Python](https://github.com/slackapi/python-slack-sdk)**: For enabling Slack integrations.
- **Community**: For ideas and feedback on improving the script.
