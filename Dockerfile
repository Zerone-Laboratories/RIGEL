# Use minimal base image
FROM alpine:3.19

LABEL maintainer="Zerone <omethabeyrathne3@gmail.com>"
LABEL description="Dockerized RIGEL_SERVICE with Python 3.13 built from source"

# Install system dependencies - expanded list for Python compilation
RUN apk add --no-cache \
    # Build essentials
    build-base \
    gcc \
    g++ \
    make \
    cmake \
    # Download tools
    curl \
    wget \
    # Python build dependencies
    openssl-dev \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    sqlite-dev \
    libffi-dev \
    xz-dev \
    libc-dev \
    linux-headers \
    # Additional libraries that Python might need
    ncurses-dev \
    gdbm-dev \
    libnsl-dev \
    libtirpc-dev \
    # For lxml and other packages
    libxml2-dev \
    libxslt-dev \
    # For cryptography
    rust \
    cargo \
    # For Pillow and graphics
    jpeg-dev \
    tiff-dev \
    openjpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    libwebp-dev \
    tcl-dev \
    tk-dev \
    harfbuzz-dev \
    fribidi-dev \
    # Other useful libraries
    cairo-dev \
    gobject-introspection-dev \
    xmlsec-dev \
    ca-certificates \
    git \
    # Clean up package manager cache is automatic with --no-cache

# Set Python version
ENV PYTHON_VERSION=3.13.0

# Set environment variables for Python build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Help Python find OpenSSL on Alpine
    CFLAGS="-I/usr/include" \
    LDFLAGS="-L/usr/lib" \
    # Ensure pip uses the right architecture
    PIP_NO_CACHE_DIR=1

# Download and build Python 3.13 from source
RUN mkdir -p /src && \
    cd /src && \
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz && \
    tar xzf Python-${PYTHON_VERSION}.tgz && \
    cd Python-${PYTHON_VERSION} && \
    # Configure with proper flags for Alpine
    ./configure \
        --prefix=/usr/local \
        --enable-optimizations \
        --enable-shared \
        --with-system-ffi \
        --with-computed-gotos \
        --enable-loadable-sqlite-extensions \
        --without-ensurepip && \
    make -j$(nproc) && \
    make altinstall && \
    # Clean up source files to reduce image size
    cd / && \
    rm -rf /src/Python-${PYTHON_VERSION}* && \
    # Create symlinks for python and pip
    ln -sf /usr/local/bin/python3.13 /usr/local/bin/python3 && \
    ln -sf /usr/local/bin/python3.13 /usr/local/bin/python && \
    # Install pip separately (more reliable on Alpine)
    wget https://bootstrap.pypa.io/get-pip.py && \
    python3.13 get-pip.py && \
    rm get-pip.py && \
    ln -sf /usr/local/bin/pip3.13 /usr/local/bin/pip3 && \
    ln -sf /usr/local/bin/pip3.13 /usr/local/bin/pip && \
    # Update pip, setuptools, and wheel
    pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy only requirements first (for better caching)
COPY requirements.txt .

# Install Python packages with proper flags for Alpine
RUN pip install --no-cache-dir \
    --no-binary :all: \
    --only-binary numpy,pandas,scipy,scikit-learn,pillow,cryptography \
    -r requirements.txt || \
    # Fallback: Try installing without restrictions if the above fails
    pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# Create a non-root user for security (optional but recommended)
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (adjust if needed)
EXPOSE 8000

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 8000)); s.close()"

# Run your server
CMD ["python", "web_server_v2.py"]