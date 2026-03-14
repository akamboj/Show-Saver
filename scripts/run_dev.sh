#!/usr/bin/env bash
# Run from project root dir

# Check if Docker engine is running
if ! sudo docker info > /dev/null 2>&1; then
    echo "Docker engine is not running. Please start Docker and try again."
    exit 1
fi

echo "Docker is ready."
docker compose -f ./compose.dev.yaml up --build
