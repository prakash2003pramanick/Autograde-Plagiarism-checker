FROM python:3.12.2

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libpoppler-cpp-dev \
    poppler-utils \
    build-essential \
    libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip and install Python dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Download NLTK models
RUN python -m nltk.downloader punkt

# Copy source code
COPY . .

# Create necessary upload directories
RUN mkdir -p uploads/UPLOAD_FOLDER uploads/HANDWRITTEN_FOLDER uploads/CONTEXT_FOLDER uploads/submissions

# Expose port
EXPOSE 80

# Run Flask development server
CMD ["bash", "build.sh"]
