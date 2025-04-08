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
main_bp = Blueprint('main', __name__)


def download_drive_file(file_id, access_token):
    """
    Download a file from Google Drive using the file ID and an access token
    
    Args:
        file_id (str): The Google Drive file ID
        access_token (str): OAuth2 access token for Google Drive API
        
    Returns:
        bytes: The file content or None if download failed
    """
    # Using the Google Drive API v3 endpoint to download file content
    download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    
    # Set up authentication headers with the access token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        print(f"Downloading file {file_id} using access token")
        response = requests.get(download_url, headers=headers)
        
        if response.status_code == 200:
            print(f"Successfully downloaded file {file_id}")
            return response.content
        else:
            print(f"Failed to download file: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
            # If token expired (401) or insufficient permissions (403), provide more info
            if response.status_code == 401:
                print("Authentication failed: Access token may be expired")
            elif response.status_code == 403:
                print("Access denied: Insufficient permissions to access this file")
            
            return None
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return None
    
@main_bp.route('/')
def index():
    return "Hello from Flask"
   

@main_bp.route('/process_assignments', methods=['POST'])
def process_assignments():
    """
    Comprehensive assignment processing endpoint 
    """
    try:
        data = request.json

        # Get access token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        access_token = auth_header.split(' ')[1]

        if not data or 'courseWork' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

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
            
        print("description", assignmentDescription)

        submissions = data['courseWork']
        print(f"Received {len(submissions)} submissions to process")

        context_folder = current_app.config['CONTEXT_FOLDER']
        submissions_path = current_app.config['SUBMISSIONS_FOLDER']

        pdf_context_extract = assignmentDescription  # Add your PDF context if needed
        assignments_text = {}

        for submission in submissions:
            try:
                if 'assignmentSubmission' in submission and 'attachments' in submission['assignmentSubmission']:
                    for attachment in submission['assignmentSubmission']['attachments']:
                        try:
                            if 'driveFile' in attachment:
                                drive_file = attachment['driveFile']
                                file_id = drive_file['id']
                                file_name = drive_file.get('title')

                                if isinstance(file_name, str) and file_name.lower().endswith('.pdf'):
                                    file_content = download_drive_file(file_id, access_token)
                                    if file_content:
                                        safe_filename = file_name.replace(" ", "_")
                                        save_path = os.path.join(submissions_path, safe_filename)

                                        with open(save_path, 'wb') as f:
                                            f.write(file_content)
                                        print(f"File saved permanently at: {save_path}")

                                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                                            temp_file.write(file_content)
                                            temp_path = temp_file.name

                                        try:
                                            extracted_text = extract_text_from_pdf(temp_path)
                                            if extracted_text:
                                                key = f"{submission['id']}_{file_name}"
                                                assignments_text[key] = {
                                                    'text': extracted_text,
                                                    'submission_id': submission['id'],
                                                    'user_id': submission['userId'],
                                                    'file_name': file_name
                                                }
                                            else:
                                                print(f"Warning: No text extracted from {file_name}")
                                        except Exception as e:
                                            print(f"Error extracting text from {file_name}: {str(e)}")
                                        finally:
                                            os.unlink(temp_path)
                                    else:
                                        print(f"Could not download file: {file_name}")
                        except Exception as e:
                            print(f"Error processing attachment: {str(e)}")
            except Exception as e:
                print(f"Error processing submission: {str(e)}")

        print("Text extraction completed.")

        # MinHash and plagiarism detection
        try:
            minhash_dict = {
                key: compute_min_hash_for_text(item['text']) for key, item in assignments_text.items()
            }

            plagiarism_scores = calculate_plagiarism_scores(minhash_dict, assignments_text)
        except Exception as e:
            return jsonify({'error': f'Error during plagiarism detection: {str(e)}'}), 500

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
                    Please thoroughly grade the following assignment on the topic of {assignmentDescription}.
                    Your evaluation should address the following aspects:
                    1. **Clarity and Organization:** Assess how clearly the assignment is written and how well the content is structured.
                    2. **Technical Accuracy and Depth:** Evaluate the correctness and depth of technical details related to {assignmentDescription}, including both theoretical understanding and practical application.
                    3. **Relevance to the Topic:** Check if the assignment covers key points, such as critical issues, innovative approaches, and context-specific challenges relevant to {assignmentDescription}.
                    4. **Analytical Rigor:** Critically analyze the argumentation, supporting data, and reasoning presented.
                    5. **Overall Coherence:** Consider the logical flow and coherence of the overall assignment.

                    Please grade the assignment at a {difficulty_level} level and provide a numerical grade out of {MAX_SCORE} along with detailed, constructive feedback highlighting both strengths and areas for improvement.
                    Make sure that the provided assignment work or extract aligns with the topic correctly.
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

                # Penalty grading
                for key in assignments_text.keys():
                    if key not in selected_for_grading:
                        plagiarism_percent = plagiarism_scores.get(key, 100)
                        penalty_grade = max(0, int(60 - plagiarism_percent))
                        group_grades[key] = {
                            'grade': penalty_grade,
                            'feedback': f"High similarity detected with other submissions ({round(plagiarism_percent, 1)}%). Please ensure your work is original."
                        }

            else:
                group_grades = {}
                for key in assignments_text.keys():
                    plagiarism_percent = plagiarism_scores.get(key, 100)
                    penalty_grade = max(0, int(60 - plagiarism_percent))
                    group_grades[key] = {
                        'grade': penalty_grade,
                        'feedback': f"High similarity detected with other submissions ({round(plagiarism_percent, 1)}%). Please ensure your work is original."
                    }

        except Exception as e:
            return jsonify({'error': f'Error during grading: {str(e)}'}), 500

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
            'grading_results': grading_results
        })

    except Exception as e:
        print(f"Unexpected server error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}"}), 500
