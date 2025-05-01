#!/usr/bin/env bash
set -o errexit

# Build and tag the image
docker build -t flask-grader-app .
docker tag flask-grader-app prakash13579/autograde:latest

# Run the container
docker run --env-file .env -p 8080:8080 prakash13579/autograde

# Push to Docker Hub
# docker push prakash13579/autograde:latest
