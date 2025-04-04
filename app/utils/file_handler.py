from flask import current_app
from pdf2image import convert_from_path
import pytesseract

def allowed_file(filename):
    """
    Check if the file has an allowed extension
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using pdf2image and pytesseract
    """
    try:
        pages = convert_from_path(pdf_path, dpi=200)
    except Exception as e:
        print(f"Error converting {pdf_path}: {e}")
        return ""

    text = ""
    for page in pages:
        page_text = pytesseract.image_to_string(page)
        text += page_text + "\n"

    print(f"Extracted text from {pdf_path}")
    return text