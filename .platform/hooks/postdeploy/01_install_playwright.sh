#!/bin/bash
set -e

echo "Installing Playwright browsers..."

# Activate virtual environment
source /var/app/venv/*/bin/activate

# Install Playwright browsers with dependencies
playwright install chromium --with-deps

echo "Playwright installation complete!"
