# Autograde-Plagiarism-Checker

Autograde-Plagiarism-Checker is an automated system that combines powerful plagiarism detection with AI-powered evaluation of academic assignments. The system analyzes PDF submissions to detect similar content across assignments, groups similar submissions for efficient processing, and provides detailed feedback and numerical grades using Google's Gemini 2.0 Flash API.

## Features

- **PDF Text Extraction**: Converts uploaded PDF assignments to text for analysis
- **Plagiarism Detection**: Uses MinHash and Jaccard similarity to identify potential plagiarism
- **Similarity Grouping**: Groups similar assignments using TF-IDF and cosine similarity
- **AI-Powered Grading**: Leverages Gemini API for comprehensive assignment evaluation
- **Context Enhancement**: Optional context PDFs can provide assignment guidelines or rubrics
- **Detailed Feedback**: Provides both numerical grades and detailed qualitative feedback
- **API Interface**: Simple REST API for easy integration with other systems

## System Requirements

- Python 3.8+
- Tesseract OCR engine

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/saurav1729/Autograde-Plagiarism-checker.git
   cd Autograde-Plagiarism-checker
   ```

2. Install dependencies:
   

3. Install Tesseract OCR:
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
   - **macOS**: `brew install tesseract`
   - **Windows**: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)



4. Create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Project Structure


## Usage

1. Start the application:
   ```
   python run.py
   ```

2. Send POST requests to the endpoint:
   ```
   POST http://localhost:5000/process_assignments
   ```

   Request body (multipart/form-data):
   - `files`: Multiple PDF files containing student assignments
   - `context_pdf` (optional): A PDF containing assignment instructions or rubric

3. Response format:
   ```json
   {
     "overall_avg_plagiarism": 15.75,
     "grading_results": {
       "assignment1.pdf": {
         "grade": 85,
         "feedback": "Detailed feedback on strengths and weaknesses...",
         "plagiarism_score": 12.5
       },
       "assignment2.pdf": {
         "grade": 72,
         "feedback": "Detailed feedback on another assignment...",
         "plagiarism_score": 19.0
       }
     }
   }
   ```

## Configuration

Key configuration options in `app/config.py`:

- `PLAGIARISM_THRESHOLD`: Maximum plagiarism percentage allowed (default: 30%)
- `GROUP_SIMILARITY_THRESHOLD`: Cosine similarity threshold for grouping (default: 0.8)
- `MAX_CONTENT_LENGTH`: Maximum file size (default: 16MB)
- `ALLOWED_EXTENSIONS`: Accepted file types (default: PDF only)

## API Reference

### Process Assignments

**Endpoint**: `/process_assignments`

**Method**: POST

**Request Parameters**:
- `files`: (Required) One or more PDF files to process
- `context_pdf`: (Optional) PDF file with assignment context

**Response**:
- `overall_avg_plagiarism`: Average plagiarism score across all assignments
- `grading_results`: Object containing results for each processed file
  - `grade`: Numerical grade (0-100)
  - `feedback`: Detailed assignment feedback
  - `plagiarism_score`: Plagiarism percentage for this assignment

## Development

1. Enable debug mode in `run.py`:
   ```python
   app.run(debug=True)
   ```


## Acknowledgments

- Uses Google's Gemini API for assignment evaluation
- MinHash implementation from DataSketch
- PDF processing with pdf2image and Tesseract OCR

## Repository

This project is available at: [https://github.com/saurav1729/Autograde-Plagiarism-checker](https://github.com/saurav1729/Autograde-Plagiarism-checker)