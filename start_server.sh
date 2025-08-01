#!/bin/bash

# Memory optimization environment variables
export PYTHONOPTIMIZE=1  # Enable Python optimizations
export PYTHONDONTWRITEBYTECODE=1  # Don't write .pyc files
export PYTHONUNBUFFERED=1  # Force stdout/stderr to be unbuffered

# gRPC optimizations for Gemini (reduces memory usage)
export GRPC_POLL_STRATEGY=poll
export GRPC_ENABLE_FORK_SUPPORT=0
export GRPC_VERBOSITY=ERROR  # Reduce gRPC logging

# Python garbage collection tuning
export PYTHONGC=1

# Set memory limits (adjust based on your server's available RAM)
ulimit -v 512000  # Virtual memory limit: 500MB

echo "Starting blogcreator server with memory optimizations..."
echo "Available memory:"
free -h

# Start with optimized gunicorn configuration
gunicorn --config gunicorn.conf.py app:app

echo "Server stopped."
