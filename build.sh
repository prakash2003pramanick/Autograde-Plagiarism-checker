#!/bin/bash

# Define image and container names
IMAGE_NAME="plagiarism-checker"
CONTAINER_NAME="plagiarism-checker-container"

# Stop and remove any existing container with the same name
docker rm -f $CONTAINER_NAME 2>/dev/null

# Build the Docker image
echo "Building Docker image..."
docker build -t $IMAGE_NAME .

# Run the Docker container with environment variables from .env file
echo "Running Docker container..."
docker run -d --env-file .env -p 80:80 --name $CONTAINER_NAME $IMAGE_NAME
