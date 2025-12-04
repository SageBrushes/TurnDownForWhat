#!/bin/bash

# Turn Down For What - Web App Startup Script

echo "Starting Turn Down For What Web App..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start the Flask app with gunicorn
echo "Starting web server on port 5000..."
echo "Access the app at http://localhost:5000"
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
