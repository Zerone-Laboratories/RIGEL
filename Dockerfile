# Use Ubuntu instead of Debian for more up-to-date packages
FROM nvidia/cuda:12.2.0-base-ubuntu22.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ARG PYTORCH_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/cu121
ARG SKIP_PYTHON_DEPS=false

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
    ca-certificates \
    xz-utils \
    tar \
    ffmpeg \
    pulseaudio-utils \
    # Additional dependencies
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    # Set up ollama directory
    && mkdir -p /etc/ollama \
    # Ensure pip is up-to-date
    && python3 -m pip install --upgrade pip -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST}

# Install Piper TTS binary at build time to avoid runtime downloads
ARG PIPER_VERSION=1.2.0
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64) PIPER_ARCH="amd64" ;; \
      aarch64|arm64) PIPER_ARCH="arm64" ;; \
      *) echo "Unsupported arch for Piper: $ARCH" && exit 1 ;; \
    esac && \
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_${PIPER_ARCH}.tar.gz" && \
    echo "Downloading Piper v${PIPER_VERSION} for ${PIPER_ARCH}..." && \
    curl -fL "$PIPER_URL" -o /tmp/piper.tar.gz && \
    mkdir -p /opt/piper && \
    tar -xzf /tmp/piper.tar.gz -C /opt/ && \
    ln -sf /opt/piper/piper /usr/local/bin/piper && \
    rm -f /tmp/piper.tar.gz && \
    echo "Piper installed at /usr/local/bin/piper"

# Piper needs its shared libraries (libespeak-ng, libonnxruntime, libpiper_phonemize)
# which are co-located in /opt/piper/
ENV LD_LIBRARY_PATH="/opt/piper:${LD_LIBRARY_PATH}"
ENV ESPEAK_DATA_PATH="/opt/piper/espeak-ng-data"

# Copy requirements first to leverage Docker cache
WORKDIR /app
COPY requirements.txt /app/

# Create symlink for python if it doesn't exist
RUN ln -sf /usr/bin/python3 /usr/bin/python || true

RUN if [ "${SKIP_PYTHON_DEPS}" = "true" ]; then \
            echo "Skipping Python dependency installation (SKIP_PYTHON_DEPS=true)"; \
        else \
            python -m pip install torch==2.5.1 torchvision torchaudio \
                --index-url ${PYTORCH_INDEX_URL} \
                --extra-index-url https://download.pytorch.org/whl/cu121 && \
            grep -Ev "^(PyGObject|torch|torchvision|torchaudio)==|^(PyGObject|torch|torchvision|torchaudio)$" requirements.txt > requirements_filtered.txt && \
            python -m pip install -r requirements_filtered.txt -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST}; \
        fi

# Copy the rest of the application code (after installing dependencies)
COPY . /app

# Pre-download VectorStore embedding model (ChromaDB DefaultEmbeddingFunction)
RUN if [ "${SKIP_PYTHON_DEPS}" != "true" ]; then \
        python -c "import chromadb; from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()"; \
    fi

# Ollama installation moved to entrypoint script for runtime detection

# Create directories for user data
RUN mkdir -p /app/user_tools /app/user_rag

# Add entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["python", "dbus_server.py"]
