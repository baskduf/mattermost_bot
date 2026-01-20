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

echo "Installing Playwright browsers..."

# Activate virtual environment
source /var/app/venv/*/bin/activate

# Install Playwright browsers (without --with-deps since we installed manually)
playwright install chromium || true

echo "Playwright installation complete!"
