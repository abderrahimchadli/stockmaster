#!/bin/bash
# Install StockMaster as a systemd service

# Ensure we're running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Path definitions
SERVICE_NAME="stockmaster"
SERVICE_FILE="stockmaster.service"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_PATH="${SCRIPT_DIR}/${SERVICE_FILE}"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_FILE}"

echo "Installing StockMaster service..."

# Make scripts executable
chmod +x "${SCRIPT_DIR}/shopify_service.py"
chmod +x "${SCRIPT_DIR}/auto_install.py"
echo "Made scripts executable"

# Install service file
cp "${SERVICE_PATH}" "${SYSTEMD_PATH}"
echo "Copied service file to ${SYSTEMD_PATH}"

# Set proper permissions for service file
chmod 644 "${SYSTEMD_PATH}"

# Reload systemd to recognize the new service
systemctl daemon-reload
echo "Reloaded systemd daemon"

# Enable the service to start at boot
systemctl enable "${SERVICE_NAME}"
echo "Enabled ${SERVICE_NAME} service to start at boot"

# Start the service
systemctl start "${SERVICE_NAME}"
echo "Started ${SERVICE_NAME} service"

# Show service status
systemctl status "${SERVICE_NAME}"

echo ""
echo "Installation complete! The service is now running and will start automatically on system boot."
echo "To check the service status: systemctl status ${SERVICE_NAME}"
echo "To view logs: journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "If you need to modify environment variables, edit the service file:"
echo "sudo nano ${SYSTEMD_PATH}"
echo "Then reload the daemon and restart the service:"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl restart ${SERVICE_NAME}" 