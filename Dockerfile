# CRIMINAL SIGNAL FLZTRGT - Web (noVNC) runner
# No code changes inside the app. Runs Tk/CustomTkinter UI in a virtual X server

FROM python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps: Tk, Xvfb, VNC, minimal WM, noVNC+websockify, fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk xvfb x11vnc fluxbox novnc websockify ca-certificates \
    fonts-dejavu-core xfonts-base && \
    rm -rf /var/lib/apt/lists/*

# App deps
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code
COPY . /app

# Start script
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

EXPOSE 8080
CMD ["/bin/bash", "/app/start.sh"]
