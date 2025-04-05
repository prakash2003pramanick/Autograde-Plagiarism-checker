import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base folders
    UPLOAD_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    
    # Upload folders
    UPLOAD_FOLDER = os.path.join(UPLOAD_BASE, 'UPLOAD_FOLDER')
    HANDWRITTEN_FOLDER = os.path.join(UPLOAD_BASE, 'HANDWRITTEN_FOLDER')
    CONTEXT_FOLDER = os.path.join(UPLOAD_BASE, 'CONTEXT_FOLDER')
    SUBMISSIONS_FOLDER = os.path.join(UPLOAD_BASE, 'submissions')
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # API settings
    API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Plagiarism thresholds
    PLAGIARISM_THRESHOLD = 30  # Percentage
    GROUP_SIMILARITY_THRESHOLD = 0.8  # Cosine similarity