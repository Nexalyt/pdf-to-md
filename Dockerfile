# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first
COPY . .

# Install Python dependencies (now that all files are copied)
RUN pip install --no-cache-dir -e .[api,pipeline,vlm]

# Download required models during build
RUN mineru-models-download --auto

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