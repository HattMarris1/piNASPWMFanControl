#!/bin/bash
# Installation script for piNASPWMFanControl

set -e

echo "==============================================="
echo "  piNASPWMFanControl Installation Script"
echo "==============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: Cannot detect Raspberry Pi model"
else
    MODEL=$(cat /proc/device-tree/model)
    echo "Detected: $MODEL"
    if [[ ! "$MODEL" == *"Raspberry Pi 5"* ]]; then
        echo "Warning: This script is designed for Raspberry Pi 5"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

echo ""
echo "Step 1: Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip hddtemp smartmontools

echo ""
echo "Step 2: Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Step 3: Creating installation directory..."
mkdir -p /opt/piNASPWMFanControl

echo ""
echo "Step 4: Copying files..."
cp fan_control.py /opt/piNASPWMFanControl/
chmod +x /opt/piNASPWMFanControl/fan_control.py

if [ ! -f /opt/piNASPWMFanControl/config.json ]; then
    echo "Creating default config.json..."
    cp config.json.example /opt/piNASPWMFanControl/config.json
    echo ""
    echo "IMPORTANT: Please edit /opt/piNASPWMFanControl/config.json"
    echo "to configure GPIO pins and HDD devices for your setup."
else
    echo "Config file already exists, skipping..."
fi

echo ""
echo "Step 5: Installing systemd service..."
cp fan-control.service /etc/systemd/system/
systemctl daemon-reload

echo ""
echo "==============================================="
echo "  Installation Complete!"
echo "==============================================="
echo ""
echo "Next steps:"
echo "1. Edit configuration: sudo nano /opt/piNASPWMFanControl/config.json"
echo "2. Test the script: sudo python3 /opt/piNASPWMFanControl/fan_control.py"
echo "3. Enable auto-start: sudo systemctl enable fan-control.service"
echo "4. Start the service: sudo systemctl start fan-control.service"
echo "5. Check status: sudo systemctl status fan-control.service"
echo ""
echo "For logs: sudo journalctl -u fan-control.service -f"
echo ""
