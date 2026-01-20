#!/bin/bash

echo "Installing Playwright dependencies for Amazon Linux..."

# Install dependencies manually for Amazon Linux 2023
sudo dnf install -y \
    alsa-lib \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXi \
    libXrandr \
    libXScrnSaver \
    libXtst \
    pango \
    at-spi2-atk \
    libdrm \
    mesa-libgbm \
    nss \
    nspr \
    libxkbcommon \
    dbus-libs \
    || true

echo "Installing Playwright browsers as webapp user..."

# Activate virtual environment and install as webapp user
source /var/app/venv/*/bin/activate

# Install Playwright browsers as webapp user (the user that runs the app)
sudo -u webapp bash -c "source /var/app/venv/*/bin/activate && playwright install chromium" || true

echo "Playwright installation complete!"
