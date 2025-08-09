# Use minimal base image
FROM debian:bullseye-slim

LABEL maintainer="Zerone <omethabeyrathne3@gmail.com>"
LABEL description="Dockerized RIGEL_SERVICE with Python 3.13 built from source"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    cmake \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libffi-dev \
    xz-utils \
    cairo \
    libgirepository-2.0-dev \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set Python version
ENV PYTHON_VERSION=3.13.0

# Download and build Python 3.13 from source
RUN cd /usr/src && \
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz && \
    tar xzf Python-${PYTHON_VERSION}.tgz && \
    cd Python-${PYTHON_VERSION} && \
    ./configure --enable-optimizations && \
    make -j"$(nproc)" && \
    make altinstall && \
    ln -s /usr/local/bin/python3.13 /usr/local/bin/python && \
    ln -s /usr/local/bin/pip3.13 /usr/local/bin/pip && \
    cd / && rm -rf /usr/src/Python-${PYTHON_VERSION}*

# Set working directory
WORKDIR /app

# Copy only requirements first (for better caching)
COPY requirements.txt .

# Install Python packages globally (no virtualenv)
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# Expose port (adjust if needed)
EXPOSE 8000

# Run your server
CMD ["python", "web_server_v2.py"]
