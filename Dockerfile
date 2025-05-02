# Use official Ubuntu base image
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    tesseract-ocr \
    poppler-utils \
    libpoppler-cpp-dev \
    build-essential \
    libffi-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Use python3.12 as default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK models
RUN python -m nltk.downloader punkt

# Copy the rest of your app
COPY . .

# Create necessary upload directories
RUN mkdir -p uploads/UPLOAD_FOLDER uploads/HANDWRITTEN_FOLDER uploads/CONTEXT_FOLDER uploads/submissions

# Expose the port your app runs on
EXPOSE 80

# Run the app
CMD ["python", "run.py"]