from flask import current_app
import pytesseract
from pdf2image import convert_from_bytes
import time
import io

def allowed_file(filename):
    """
    Check if the file has an allowed extension
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
           
           


def extract_text_from_pdf(pdf_bytes):
    """
    Extract text from a PDF file using pdf2image and pytesseract directly from bytes
    without storing the file on disk
    """
    try:
        # Convert PDF bytes to images directly
        pages = convert_from_bytes(
            pdf_bytes, 
            dpi=300,  # Higher DPI for better OCR quality
            thread_count=4  # Use multiple threads for faster conversion
        )
        
        print(f"Converted PDF to {len(pages)} images")
        
        # Process each page with OCR
        texts = []
        for i, img in enumerate(pages, start=1):
            start = time.time()
            # Apply some preprocessing to improve OCR quality if needed
            # img = img.convert('L')  # Convert to grayscale if needed
            
            # Perform OCR
            txt = pytesseract.image_to_string(img)
            duration = time.time() - start
            print(f"OCR took {duration:.2f}s for page {i}")
            
            # Add page number and text to results
            texts.append(f"--- Page {i} ---\n{txt}")
        
        # Combine all text
        full_text = "\n".join(texts)
        print(f"Extracted total of {len(full_text)} characters from PDF")
        return full_text
        
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return f"Error extracting text: {str(e)}"