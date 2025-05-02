# Use official Python image
FROM python:3.12-slim

# Set environment to non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Install system-level dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libpoppler-cpp-dev \
    build-essential \
    libffi-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download required NLTK models
RUN python -m nltk.downloader punkt

# Copy project files
COPY . .

# Create upload directories
RUN mkdir -p uploads/UPLOAD_FOLDER uploads/HANDWRITTEN_FOLDER uploads/CONTEXT_FOLDER uploads/submissions

# Expose application port
EXPOSE 80

# Run the app
CMD ["python", "run.py"]