import os
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.utils.file_handler import allowed_file, extract_text_from_pdf
from app.utils.text_analysis import compute_min_hash_for_text
from app.utils.plagiarism import calculate_plagiarism_scores, group_similar_assignments
from app.utils.grading import call_gemini_api_cached
import tempfile
import requests
import re
import io
from urllib.parse import urlparse, parse_qs
main_bp = Blueprint('main', __name__)

def fetch_pdf_bytes(url, access_token):
    """
    Download PDF bytes from Google Drive URL or direct URL
    
    Args:
        url: Google Drive share URL or direct URL to PDF
        access_token: OAuth access token for Google Drive API
        
    Returns:
        bytes: Raw PDF content as bytes
    """
    
    # Create a session for connection pooling
    session = requests.Session()
    
    # Extract file ID if it's a Google Drive URL
    file_id = extract_drive_file_id(url)
    
    if file_id:
        print(f"Detected Google Drive file ID: {file_id}")
        
        # Try multiple methods to download the file
        pdf_bytes = None
        errors = []
        
        # Method 1: Direct API access with token
        if access_token:
            try:
                # Use the direct download URL
                download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
                headers = {
                    "Authorization": f"Bearer {access_token}"
                }
                
                print(f"Method 1: Trying API download with access token")
                resp = session.get(download_url, headers=headers, stream=True, timeout=30)
                resp.raise_for_status()
                pdf_bytes = resp.content
                print(f"Method 1: Successfully downloaded {len(pdf_bytes)} bytes")
                return pdf_bytes
            except requests.RequestException as e:
                errors.append(f"Method 1 failed: {str(e)}")
                print(errors[-1])
        
        # Method 2: Using the export=download parameter (works for publicly accessible files)
        try:
            print(f"Method 2: Trying public download link")
            direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            resp = session.get(direct_url, stream=True, timeout=30)
            resp.raise_for_status()
            
            # Check if we need to confirm download (large files)
            if 'text/html' in resp.headers.get('Content-Type', ''):
                # Extract confirmation token
                confirm_token = None
                for k, v in session.cookies.items():
                    if k.startswith('download_warning'):
                        confirm_token = v
                        break
                
                # If token found, make a second request with confirmation
                if confirm_token:
                    print(f"Method 2: Large file detected, confirming download with token")
                    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                    resp = session.get(direct_url, stream=True, timeout=30)
                    resp.raise_for_status()
            
            pdf_bytes = resp.content
            
            # Validate PDF header
            if pdf_bytes.startswith(b'%PDF'):
                print(f"Method 2: Successfully downloaded {len(pdf_bytes)} bytes")
                return pdf_bytes
            else:
                errors.append(f"Method 2: Downloaded content is not a valid PDF")
                print(errors[-1])
        except requests.RequestException as e:
            errors.append(f"Method 2 failed: {str(e)}")
            print(errors[-1])
        
        # Method 3: Try the files.get endpoint with fields=webContentLink
        if access_token:
            try:
                print(f"Method 3: Getting webContentLink via API")
                metadata_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=webContentLink"
                headers = {
                    "Authorization": f"Bearer {access_token}"
                }
                
                resp = session.get(metadata_url, headers=headers, timeout=30)
                resp.raise_for_status()
                metadata = resp.json()
                
                if 'webContentLink' in metadata:
                    content_link = metadata['webContentLink']
                    print(f"Method 3: Got webContentLink: {content_link}")
                    
                    resp = session.get(content_link, stream=True, timeout=30)
                    resp.raise_for_status()
                    pdf_bytes = resp.content
                    
                    if pdf_bytes.startswith(b'%PDF'):
                        print(f"Method 3: Successfully downloaded {len(pdf_bytes)} bytes")
                        return pdf_bytes
                    else:
                        errors.append(f"Method 3: Downloaded content is not a valid PDF")
                        print(errors[-1])
                else:
                    errors.append(f"Method 3: No webContentLink available")
                    print(errors[-1])
            except requests.RequestException as e:
                errors.append(f"Method 3 failed: {str(e)}")
                print(errors[-1])
            except ValueError as e:
                errors.append(f"Method 3 JSON error: {str(e)}")
                print(errors[-1])
        
        # If we reached here, all methods failed
        error_msg = "All download methods failed:\n" + "\n".join(errors)
        print(error_msg)
        raise Exception(error_msg)
    else:
        # Direct download for non-Drive URLs
        print(f"Direct download from URL: {url}")
        try:
            resp = session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error downloading from URL: {e}")
            raise
    
    # Check if we got a PDF
    content_type = resp.headers.get('Content-Type', '')
    if 'application/pdf' not in content_type and not url.lower().endswith('.pdf'):
        print(f"Warning: Content type '{content_type}' may not be a PDF")
    
    # Read all content into a BytesIO buffer
    buf = io.BytesIO()
    total_size = 0
    
    for chunk in resp.iter_content(chunk_size=8192):
        if chunk:
            buf.write(chunk)
            total_size += len(chunk)
            
    print(f"Downloaded {total_size} bytes")
    
    # Get the bytes from the buffer
    pdf_bytes = buf.getvalue()
    
    # Basic validation - PDF files start with '%PDF'
    if not pdf_bytes.startswith(b'%PDF'):
        print("Warning: Downloaded content doesn't appear to be a valid PDF")
        print(f"First 20 bytes: {pdf_bytes[:20]}")
    
    return pdf_bytes

def extract_drive_file_id(url):
    """
    Extract Google Drive file ID from various formats of Google Drive URLs
    """
    import re
    from urllib.parse import urlparse, parse_qs
    
    # Check if it's a standard Google Drive URL
    if 'drive.google.com' in url:
        # Pattern for '/d/<id>' or '/file/d/<id>' format
        id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if id_match:
            return id_match.group(1)
            
        # Pattern for 'id=<id>' format (used in older Drive links)
        id_param = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if id_param:
            return id_param.group(1)
            
        # Try to parse as URL and extract ID from query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        if 'id' in query_params:
            return query_params['id'][0]
    
    # Check if this is already just a file ID
    if re.match(r'^[a-zA-Z0-9_-]{25,}$', url.strip()):
        return url.strip()
    
    # Not a Google Drive URL or ID not found
    return None

def verify_access_token(access_token):
    """
    Verify if the access token is valid and has the required scopes
    
    Args:
        access_token: OAuth access token for Google Drive API
        
    Returns:
        bool: True if token is valid, False otherwise
        dict: Token information if valid
    """
    import requests
    
    # Google's token info endpoint
    token_info_url = f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
    
    try:
        response = requests.get(token_info_url, timeout=10)
        
        if response.status_code == 200:
            token_info = response.json()
            
            # Check if token has drive scope
            required_scope = "https://www.googleapis.com/auth/drive"
            scopes = token_info.get('scope', '').split(' ')
            
            has_drive_scope = False
            for scope in scopes:
                if scope == required_scope or scope.startswith(required_scope + '.'):
                    has_drive_scope = True
                    break
            
            if not has_drive_scope:
                print("Token is valid but lacks Drive scope!")
                return False, token_info
            
            # Check expiration
            expires_in = int(token_info.get('expires_in', 0))
            if expires_in < 60:  # Less than a minute
                print(f"Token will expire soon! Only {expires_in} seconds left")
            
            print(f"Access token is valid for {expires_in} more seconds")
            return True, token_info
        else:
            print(f"Token validation failed: {response.status_code}")
            print(response.text)
            return False, None
    except Exception as e:
        print(f"Error validating token: {str(e)}")
        return False, None

# Add to the process_assignments route
def validate_request(request_data, access_token):
    """
    Validate the incoming request data and access token
    
    Args:
        request_data: The request JSON data
        access_token: The OAuth access token
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check required fields
    if not request_data or 'courseWork' not in request_data:
        return False, "Missing 'courseWork' field in request"
    
    # Validate access token
    is_valid, token_info = verify_access_token(access_token)
    if not is_valid:
        return False, "Invalid or expired access token"
    
    # Check submissions format
    submissions = request_data['courseWork']
    if not isinstance(submissions, list) or len(submissions) == 0:
        return False, "No valid submissions found in request"
    
    # Success
    return True, ""


@main_bp.route('/')
def index():
    return "Hello from Flask"
   

@main_bp.route('/process_assignments', methods=['POST'])
def process_assignments():
    """
    Comprehensive assignment processing endpoint that processes PDF bytes directly
    without storing files on disk
    """
    try:
        data = request.json
        
        print("Incoming request:", data)

        # Get access token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        access_token = auth_header.split(' ')[1]

        # Validate request and access token
        is_valid, error_message = validate_request(data, access_token)
        if not is_valid:
            return jsonify({'error': error_message}), 400

        # Get assignment information
        assignmentDescription = "Title description"
        assignmentTitle = "title"
        MAX_SCORE = 100

        try:
            assignmentInfo = data.get('assignmentInfo')
            if assignmentInfo:
                assignmentTitle = assignmentInfo.get('title', 'Untitled')
                assignmentDescription = assignmentInfo.get('description', '')
                MAX_SCORE = assignmentInfo.get('maxPoints', 100)
        except Exception as e:
            print(f"Error parsing assignment info: {str(e)}")
            
        print("Assignment description:", assignmentDescription)

        submissions = data['courseWork']
        print(f"Received {len(submissions)} submissions to process")

        pdf_context_extract = assignmentDescription
        assignments_text = {}
        failed_submissions = []

        # Process each submission
        for submission in submissions:
            try:
                if 'assignmentSubmission' not in submission or 'attachments' not in submission['assignmentSubmission']:
                    failed_submissions.append({
                        'submission_id': submission.get('id', 'unknown'),
                        'error': 'Missing assignment submission or attachments'
                    })
                    continue
                    
                for attachment in submission['assignmentSubmission']['attachments']:
                    if 'driveFile' not in attachment:
                        continue
                        
                    drive_file = attachment['driveFile']
                    file_id = drive_file['id']
                    file_name = drive_file.get('title')

                    # Only process PDF files
                    if not isinstance(file_name, str) or not file_name.lower().endswith('.pdf'):
                        print(f"Skipping non-PDF file: {file_name}")
                        continue
                        
                    pdf_url = drive_file.get('alternateLink')
                    if not pdf_url:
                        print(f"Missing alternateLink in drive file for {file_name}")
                        failed_submissions.append({
                            'submission_id': submission.get('id', 'unknown'),
                            'file_name': file_name,
                            'error': 'Missing alternateLink in drive file'
                        })
                        continue
                        
                    print(f"Processing PDF URL: {pdf_url}")
                    
                    try:
                        # Try to download PDF with our improved method
                        pdf_bytes = fetch_pdf_bytes(pdf_url, access_token)
                        print(f"Downloaded {len(pdf_bytes)} bytes from {pdf_url}")
                        
                        # Verify PDF header
                        if pdf_bytes[:4] != b'%PDF':
                            error_msg = f"Downloaded content doesn't appear to be a valid PDF for {file_name}"
                            print(f"Warning: {error_msg}")
                            failed_submissions.append({
                                'submission_id': submission.get('id', 'unknown'),
                                'file_name': file_name,
                                'error': error_msg
                            })
                            continue
                        
                        # Extract text directly from PDF bytes
                        extracted_text = extract_text_from_pdf(pdf_bytes)
                        
                        if extracted_text:
                            key = f"{submission['id']}_{file_name}"
                            assignments_text[key] = {
                                'text': extracted_text,
                                'submission_id': submission['id'],
                                'user_id': submission['userId'],
                                'file_name': file_name
                            }
                        else:
                            error_msg = f"No text could be extracted from {file_name}"
                            print(f"Warning: {error_msg}")
                            failed_submissions.append({
                                'submission_id': submission.get('id', 'unknown'),
                                'file_name': file_name,
                                'error': error_msg
                            })
                            
                        del pdf_bytes
                            
                    except Exception as e:
                        error_msg = f"Error processing PDF {file_name}: {str(e)}"
                        print(error_msg)
                        failed_submissions.append({
                            'submission_id': submission.get('id', 'unknown'),
                            'file_name': file_name,
                            'error': error_msg
                        })
            except Exception as e:
                print(f"Error processing submission: {str(e)}")
                failed_submissions.append({
                    'submission_id': submission.get('id', 'unknown'),
                    'error': f"Unexpected error: {str(e)}"
                })

        print(f"Text extraction completed for {len(assignments_text)} documents.")
        print(f"Failed to process {len(failed_submissions)} submissions.")

        if not assignments_text:
            return jsonify({
                'error': 'No valid submissions could be processed',
                'failed_submissions': failed_submissions
            }), 400

        # Continue with the rest of the processing...
        # MinHash and plagiarism detection
        try:
            minhash_dict = {
                key: compute_min_hash_for_text(item['text']) for key, item in assignments_text.items()
            }

            plagiarism_scores = calculate_plagiarism_scores(minhash_dict, assignments_text)
        except Exception as e:
            return jsonify({
                'error': f'Error during plagiarism detection: {str(e)}',
                'failed_submissions': failed_submissions
            }), 500

        threshold = current_app.config['PLAGIARISM_THRESHOLD']
        selected_for_grading = {
            key: item for key, item in assignments_text.items()
            if plagiarism_scores.get(key, 100) < threshold
        }

        # Grouping and grading
        try:
            if selected_for_grading:
                selected_files = list(selected_for_grading.keys())
                selected_texts = [selected_for_grading[key]['text'] for key in selected_files]

                groups = group_similar_assignments(
                    selected_texts,
                    selected_files,
                    current_app.config['GROUP_SIMILARITY_THRESHOLD']
                )

                difficulty_level = "hard"
                assignment_context = f"""
                        Please evaluate the following student assignment on the topic of "{assignmentDescription}" and generate **detailed, structured HTML feedback**. The tone should be constructive, educational, and tailored to help the student improve.

                        ---

                        **Evaluation Instructions**:

                        Break down the feedback into the following sections using styled HTML:

                        ### 1. Criteria Breakdown:
                        Evaluate based on the following five major criteria, each scored separately:
                        - Clarity and Organization (out of 20)
                        - Technical Accuracy and Depth (out of 30)
                        - Relevance to the Topic (out of 20)
                        - Analytical Rigor (out of 15)
                        - Overall Coherence (out of 15)

                        For each criterion:
                        - Assign a score (e.g., 18/30)
                        - Provide 2–5 bullet points with specific observations to justify the score

                        ### 2. Detailed Assignment Review:
                        Include a full paragraph (or two) of in-depth analysis of the student's submission. Go beyond scoring to:
                        - Acknowledge what was done well
                        - Explain what needs improvement
                        - Offer actionable suggestions on structure, content depth, clarity, and alignment with the topic
                        - Keep it supportive and growth-oriented

                        ### 3. Summary:
                        Write 1–2 concise sentences summarizing the overall performance, strengths, and areas for improvement.

                        ---

                        **Format Requirements**:

                        Return the feedback in styled HTML with spacing between sections and a clean, readable layout.

                        ```html
                        <div style="margin: 20px 0; font-family: Arial, sans-serif;">
                        <style>
                            .feedback-table {{
                            width: 100%;
                            border-collapse: collapse;
                            font-family: Arial, sans-serif;
                            font-size: 14px;
                            margin-bottom: 30px;
                            }}
                            .feedback-table th, .feedback-table td {{
                            border: 1px solid #ccc;
                            padding: 10px 14px;
                            text-align: left;
                            vertical-align: top;
                            }}
                            .feedback-table th {{
                            background-color: #f0f0f0;
                            font-weight: bold;
                            }}
                            .feedback-table tr:nth-child(even) {{
                            background-color: #fafafa;
                            }}
                            @media screen and (max-width: 600px) {{
                            .feedback-table th, .feedback-table td {{
                                padding: 8px 10px;
                                font-size: 13px;
                            }}
                            }}
                        </style>

                        <table class="feedback-table">
                            <thead>
                            <tr>
                                <th>Criteria</th>
                                <th>Feedback</th>
                                <th style="text-align:center;">Score</th>
                            </tr>
                            </thead>
                            <tbody>
                            <!-- Dynamic rows for each criterion -->
                            <tr>
                                <td>Clarity and Organization</td>
                                <td>
                                - Introduction sets context but lacks flow<br>
                                - Paragraph transitions could be smoother<br>
                                - Ideas are mostly organized but slightly repetitive
                                </td>
                                <td style="text-align:center;">14/20</td>
                            </tr>
                            <!-- Repeat for other 4 criteria -->

                            <!-- Detailed review -->
                            <tr>
                                <td colspan="3"><strong>Detailed Assignment Review</strong><br>
                                The assignment demonstrates moderate understanding of the core topic. The student made a clear attempt to address key ideas but lacked consistent depth. For instance, the analysis of {assignmentDescription} misses supporting examples or fails to elaborate on implications. Improving logical flow between sections and reinforcing claims with evidence would elevate the submission. Consider revisiting the course materials or examples to better frame arguments.
                                </td>
                            </tr>

                            <!-- Summary -->
                            <tr>
                                <td colspan="3"><strong>Summary</strong><br>
                                A fair attempt with solid effort. Key improvements in structure and depth will greatly enhance clarity and impact.
                                </td>
                            </tr>
                            </tbody>
                        </table>
                        </div>
                        """


                group_grades = {}
                print("Grading groups using Gemini API...")
                for group in groups:
                    try:
                        combined_text = "\n".join([selected_for_grading[selected_files[i]]['text'] for i in group])
                        result = call_gemini_api_cached(
                            combined_text,
                            assignment_context,
                            pdf_context_extract,
                            current_app.config['API_KEY']
                        )
                        for i in group:
                            group_grades[selected_files[i]] = result
                    except Exception as e:
                        print(f"Error grading group {group}: {str(e)}")

                # Penalty grading for plagiarized submissions
                for key in assignments_text.keys():
                    if key not in selected_for_grading:
                        plagiarism_percent = plagiarism_scores.get(key, 100)
                        penalty_grade = max(0, int(60 - plagiarism_percent))
                        group_grades[key] = {
                            'grade': penalty_grade,
                            'feedback': f"High similarity detected with other submissions ({round(plagiarism_percent, 1)}%). Please ensure your work is original."
                        }

            else:
                # All submissions have high similarity
                group_grades = {}
                for key in assignments_text.keys():
                    plagiarism_percent = plagiarism_scores.get(key, 100)
                    penalty_grade = max(0, int(60 - plagiarism_percent))
                    group_grades[key] = {
                        'grade': penalty_grade,
                        'feedback': f"High similarity detected with other submissions ({round(plagiarism_percent, 1)}%). Please ensure your work is original."
                    }

        except Exception as e:
            return jsonify({
                'error': f'Error during grading: {str(e)}',
                'failed_submissions': failed_submissions
            }), 500

        # Compile results
        submission_results = {}
        for key, result in group_grades.items():
            try:
                submission_id = assignments_text[key]['submission_id']
                submission_results[submission_id] = {
                    'user_id': assignments_text[key]['user_id'],
                    'filename': assignments_text[key]['file_name'],
                    'plagiarism_score': round(plagiarism_scores[key], 2),
                    'grade': result['grade'],
                    'feedback': result['feedback']
                }
            except Exception as e:
                print(f"Error compiling result for {key}: {str(e)}")

        overall_avg_plagiarism = round(np.mean(list(plagiarism_scores.values())), 2) if plagiarism_scores else 0.0

        grading_results = []
        for submission_id, result in submission_results.items():
            grading_results.append({
                'submission_id': submission_id,
                'user_id': result['user_id'],
                'filename': result['filename'],
                'plagiarism_score': result['plagiarism_score'],
                'grade': result['grade'],
                'feedback': result['feedback']
            })

        return jsonify({
            'overall_avg_plagiarism': overall_avg_plagiarism,
            'grading_results': grading_results,
            'failed_submissions': failed_submissions
        })

    except Exception as e:
        print(f"Unexpected server error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}"}), 500
