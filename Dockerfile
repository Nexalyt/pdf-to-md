# Multi-stage build to reduce final image size
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install core dependencies
RUN pip install --no-cache-dir \
    numpy>=1.21.6 \
    pillow>=11.0.0 \
    requests \
    click>=8.1.7 \
    loguru>=0.7.2

# Install CPU-only PyTorch to reduce size significantly
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install other ML dependencies
RUN pip install --no-cache-dir \
    transformers>=4.51.1 \
    accelerate>=1.5.1 \
    opencv-python-headless>=4.11.0.86

# Install the package itself
RUN pip install --no-cache-dir -e .[api,pipeline]

# Production stage
FROM python:3.11-slim

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Download models during build to avoid runtime delays
RUN /bin/bash -c "mineru-models-download -s huggingface -m pipeline" && \
    rm -rf /root/.cache/pip

# Create output directory with proper permissions
RUN mkdir -p /app/output && chmod 755 /app/output

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app

# Run the FastAPI application using the built-in mineru-api command
CMD ["mineru-api", "--host", "0.0.0.0", "--port", "8080"]