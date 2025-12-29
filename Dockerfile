# Use Ubuntu instead of Debian for more up-to-date packages
FROM nvidia/cuda:12.2.0-base-ubuntu22.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install Python and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    # PyGObject and GTK dependencies
    libgirepository1.0-dev \
    gir1.2-gtk-3.0 \
    libcairo2-dev \
    python3-gi \
    python3-gi-cairo \
    # GIR repository tools
    gir1.2-girepository-2.0 \
    gobject-introspection \
    # DBus dependencies
    libdbus-1-dev \
    dbus \
    # General dependencies
    git \
    curl \
    ffmpeg \
    # Additional dependencies
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    # Set up ollama directory
    && mkdir -p /etc/ollama \
    # Ensure pip is up-to-date
    && python3 -m pip install --upgrade pip

# Copy requirements first to leverage Docker cache
WORKDIR /app
COPY requirements.txt /app/

# Create symlink for python if it doesn't exist
RUN ln -sf /usr/bin/python3 /usr/bin/python || true

RUN python -m pip install torch==2.5.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install Python dependencies excluding PyGObject (before copying app code)
RUN grep -v "PyGObject" requirements.txt > requirements_filtered.txt && \
    python -m pip install -r requirements_filtered.txt

# Copy the rest of the application code (after installing dependencies)
COPY . /app

# Ollama installation moved to entrypoint script for runtime detection

# Create directories for user data
RUN mkdir -p /app/user_tools /app/user_rag

# Add entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["python", "dbus_server.py"]
