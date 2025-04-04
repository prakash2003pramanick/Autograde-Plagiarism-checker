import os
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.utils.file_handler import allowed_file, extract_text_from_pdf
from app.utils.text_analysis import compute_min_hash_for_text
from app.utils.plagiarism import calculate_plagiarism_scores, group_similar_assignments
from app.utils.grading import call_gemini_api_cached

main_bp = Blueprint('main', __name__)

@main_bp.route('/process_assignments', methods=['POST'])
def process_assignments():
    """
    Comprehensive assignment processing endpoint 
    """
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return jsonify({'error': 'No selected files'}), 400

        # Handle file uploads
        assignments_folder = current_app.config['UPLOAD_FOLDER']
        context_folder = current_app.config['CONTEXT_FOLDER']

        # Process uploaded files
        pdf_files = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(assignments_folder, filename)
                file.save(filepath)
                pdf_files.append(filepath)
            else:
                return jsonify({'error': f'Invalid file type: {file.filename}'}), 400

        if not pdf_files:
            return jsonify({'error': 'No valid PDF files uploaded'}), 400
        
        # Extract text from context PDF if provided
        pdf_context_extract = None
        if 'context_pdf' in request.files:  
            context_file = request.files['context_pdf']
            if context_file and allowed_file(context_file.filename):
                context_path = os.path.join(context_folder, secure_filename(context_file.filename))
                context_file.save(context_path)
                print(f"Extracting additional context from {context_file.filename} ...")
                pdf_context_extract = extract_text_from_pdf(context_path)
        
        # Extract text from all assignment PDFs
        assignments_text = {}
        for pdf_file in pdf_files:
            try:
               print(f"Processing {pdf_file} ...")
               extracted = extract_text_from_pdf(pdf_file)
               assignments_text[os.path.basename(pdf_file)] = extracted
            except Exception as e:
                return jsonify({'error': f'Error processing {pdf_file}: {str(e)}'}), 500
        
        print("Text extraction completed.")
        
        # Create MinHash signatures for each document
        minhash_dict = {}
        for fname, text in assignments_text.items():
            minhash_dict[fname] = compute_min_hash_for_text(text)
        
        # Calculate plagiarism scores
        plagiarism_scores = calculate_plagiarism_scores(minhash_dict, assignments_text)
        
        # Filter assignments based on plagiarism threshold
        threshold = current_app.config['PLAGIARISM_THRESHOLD']
        selected_for_grading = {fname: text for fname, text in assignments_text.items() 
                             if plagiarism_scores[fname] < threshold}
        
        print(f"\nAssignments selected for grading (max plagiarism below {threshold}%):")
        for fname in selected_for_grading:
            print(fname)
            
        if not selected_for_grading:
            return jsonify({'error': 'No assignments passed the plagiarism check'}), 400
            
        # Group similar assignments
        selected_files = list(selected_for_grading.keys())
        selected_texts = [selected_for_grading[fname] for fname in selected_files]
        
        groups = group_similar_assignments(
            selected_texts, 
            selected_files, 
            current_app.config['GROUP_SIMILARITY_THRESHOLD']
        )
        
        # Define assignment context for grading
        topic = "Fraud Detection and AI"
        difficulty_level = "hard"
        assignment_context = f"""
        Please thoroughly grade the following assignment on the topic of {topic}.
        Your evaluation should address the following aspects:
        1. **Clarity and Organization:** Assess how clearly the assignment is written and how well the content is structured.
        2. **Technical Accuracy and Depth:** Evaluate the correctness and depth of technical details related to {topic}, including both theoretical understanding and practical application.
        3. **Relevance to the Topic:** Check if the assignment covers key points, such as critical issues, innovative approaches, and context-specific challenges relevant to {topic}.
        4. **Analytical Rigor:** Critically analyze the argumentation, supporting data, and reasoning presented.
        5. **Overall Coherence:** Consider the logical flow and coherence of the overall assignment.

        Please grade the assignment at a {difficulty_level} level and provide a numerical grade out of 100 along with detailed, constructive feedback highlighting both strengths and areas for improvement.
        Make sure that the provided assignment work or extract aligns with the topic correctly.
        """

        # Grade each group
        group_grades = {}
        print("\nGrading groups using Gemini API...")

        for group in groups:
            # Combine texts from all assignments in this group
            combined_text = "\n".join([selected_for_grading[selected_files[i]] for i in group])
            # Call the Gemini API including the optional PDF context if available
            result = call_gemini_api_cached(
                combined_text, 
                assignment_context, 
                pdf_context_extract,
                current_app.config['API_KEY']
            )
            # Assign the same result to all assignments in the group
            for i in group:
                group_grades[selected_files[i]] = result
            group_files = [selected_files[i] for i in group]

        # Final Overall Plagiarism & Grading Summary
        overall_avg_plagiarism = np.mean(list(plagiarism_scores.values()))
        print(f"\nOverall average plagiarism score across assignments: {round(overall_avg_plagiarism,2)}%")

        # Prepare final results
        grading_results = {}
        for fname, result in group_grades.items():
            grading_results[fname] = {
                'grade': result['grade'], 
                'feedback': result['feedback'],
                'plagiarism_score': round(plagiarism_scores.get(fname, 0), 2)
            }
        
        return jsonify({
            'overall_avg_plagiarism': round(overall_avg_plagiarism, 2),
            'grading_results': grading_results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500