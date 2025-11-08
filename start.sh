#!/usr/bin/env bash
set -euo pipefail

# Defaults
VNC_PASSWORD=""
DISPLAY_NUM=99
DISPLAY=:$DISPLAY_NUM
SCREEN_GEOM=${SCREEN_GEOM:-1280x800x24}
NOVNC_PORT=${NOVNC_PORT:-${PORT:-8080}}
VNC_PORT=5900

# Prepare runtime dirs
mkdir -p /root/.vnc /var/log/app

# Start Xvfb
Xvfb $DISPLAY -screen 0 $SCREEN_GEOM -nolisten tcp &
XVFB_PID=$!
sleep 1

# Start a minimal WM (fluxbox)
fluxbox -display $DISPLAY >/var/log/app/fluxbox.log 2>&1 &
sleep 0.5

# Start x11vnc
x11vnc -display $DISPLAY -forever -shared -nopw -rfbport $VNC_PORT \
  >/var/log/app/x11vnc.log 2>&1 &

# Start noVNC with novnc_proxy (exposes WS at /websockify)
/usr/share/novnc/utils/novnc_proxy \
  --vnc localhost:$VNC_PORT \
  --listen 0.0.0.0:$NOVNC_PORT \
  --web /usr/share/novnc/ \
  >/var/log/app/websockify.log 2>&1 &

# Launch the app
export DISPLAY=$DISPLAY
trap 'kill $XVFB_PID || true; exit 0' SIGTERM SIGINT
exec python -u /app/main.py

# Cleanup
kill $XVFB_PID || true
