#!/usr/bin/env bash
set -o errexit

# Download NLTK data
python -c "import nltk; nltk.download('punkt' , quiet = True); nltk.download('punkt_tab')"

# Local build
docker build -t flask-grader-app .
