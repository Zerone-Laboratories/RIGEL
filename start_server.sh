#!/bin/bash

# Start script for RIGEL instanced server
echo "Starting RIGEL instanced server with docker-compose..."

# Ensure directories for user data exist
mkdir -p user_tools user_rag

# Check if GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
  echo "Warning: GROQ_API_KEY environment variable is not set."
  echo "If you want to use Groq as an inference engine, please set it:"
  echo "export GROQ_API_KEY=your_key_here"
fi

# Set default engine if not specified
if [ -z "$DEFAULT_INFERENCE_ENGINE" ]; then
  export DEFAULT_INFERENCE_ENGINE=ollama
  echo "Using default inference engine: ollama"
else
  echo "Using specified inference engine: $DEFAULT_INFERENCE_ENGINE"
fi

# Start the server with docker-compose
docker-compose up -d

# Show logs
echo "Server is starting... Showing logs:"
docker-compose logs -f
