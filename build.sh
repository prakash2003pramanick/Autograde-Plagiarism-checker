#!/usr/bin/env bash
set -o errexit

# Local build
docker build -t flask-grader-app .
