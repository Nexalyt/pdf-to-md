# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgdal-dev \
    libfontconfig1 \
    libxcb1 \
    libopencv-dev \
    pkg-config \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Update pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Copy application code first
COPY . .

# Install Python dependencies in stages to avoid memory issues
# First install core dependencies
RUN pip install --no-cache-dir \
    numpy>=1.21.6 \
    pillow>=11.0.0 \
    requests \
    click>=8.1.7 \
    loguru>=0.7.2

# Install PyTorch first (CPU version for smaller footprint)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install other ML dependencies
RUN pip install --no-cache-dir \
    transformers>=4.51.1 \
    accelerate>=1.5.1 \
    opencv-python-headless>=4.11.0.86

# Install the package itself
RUN pip install --no-cache-dir -e .[api,pipeline]

# Skip model downloads for now to avoid build timeout
# RUN mineru-models-download --auto

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