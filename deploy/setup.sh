#!/bin/bash
# Deploy quant-dashboard to 39.96.211.212
# Run as root on the target server

set -e

APP_DIR="/opt/quant-dashboard"
REPO_URL="https://github.com/viekai/quant-dashboard.git"

echo "=== Quant Dashboard Deployment ==="

# Clone or pull
if [ -d "$APP_DIR" ]; then
    echo "Updating existing installation..."
    cd "$APP_DIR" && git pull
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$APP_DIR"
fi

# Install Python dependencies
cd "$APP_DIR/backend"
pip3 install -r requirements.txt

# Create data directory
mkdir -p "$APP_DIR/backend/data"

# Install systemd service
cp "$APP_DIR/deploy/quant-dashboard.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable quant-dashboard
systemctl restart quant-dashboard

# Install nginx config
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/quant-dashboard.conf
nginx -t && systemctl reload nginx

echo ""
echo "=== Deployment complete ==="
echo "Dashboard: http://39.96.211.212/"
echo "API: http://39.96.211.212/api/status/latest"
echo ""
echo "IMPORTANT: Update DASHBOARD_TOKEN in /etc/systemd/system/quant-dashboard.service"
echo "Then run: systemctl daemon-reload && systemctl restart quant-dashboard"
