#!/bin/bash

# Exit on any error
set -e

# Set default environment variables
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8080}

# Create output directory if it doesn't exist
mkdir -p /app/output

# Start the FastAPI application using the built-in mineru-api command
exec mineru-api --host ${HOST} --port ${PORT}