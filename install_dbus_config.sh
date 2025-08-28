#!/bin/bash

# This script installs the RIGEL D-Bus configuration to the system
# Run with sudo

set -e

echo "Installing RIGEL D-Bus configuration..."

# Create the system D-Bus configuration directory if it doesn't exist
mkdir -p /etc/dbus-1/system.d/

# Copy the configuration file to the system D-Bus configuration directory
cp rigel-dbus.conf /etc/dbus-1/system.d/

# Set proper permissions
chmod 644 /etc/dbus-1/system.d/rigel-dbus.conf

# Reload D-Bus configuration
echo "Reloading D-Bus configuration..."
if systemctl is-active --quiet dbus; then
    systemctl reload dbus
else
    echo "Warning: dbus service not running or detected, manual restart may be required"
fi

echo "D-Bus configuration installed successfully"
echo "You can now start the Docker container"
