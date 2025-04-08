FROM python:3.12.2

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libpoppler-cpp-dev \
    poppler-utils \
    build-essential \
    libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK models
RUN python -m nltk.downloader punkt

# Copy source
COPY . .

# Create directories
RUN mkdir -p uploads/UPLOAD_FOLDER uploads/HANDWRITTEN_FOLDER uploads/CONTEXT_FOLDER uploads/submissions

# Port
EXPOSE 8080

# Gunicorn CMD
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run:app", "--timeout", "300"]
