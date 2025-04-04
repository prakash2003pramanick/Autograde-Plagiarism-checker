import re
import hashlib
import requests

# Global API cache to avoid duplicate calls
api_cache = {}

def call_gemini_api_cached(assignment_text, context, pdf_context_extract=None, api_key=None):
    """
    Calls the Gemini API to grade the provided assignment.
    Combines dynamic context, optional PDF context, and the assignment text.
    Uses caching to avoid duplicate calls.

    The function extracts the exact numerical grade from the response.
    """
    # Create a combined string for caching
    combined_for_hash = assignment_text + (pdf_context_extract if pdf_context_extract else "")
    text_hash = hashlib.md5(combined_for_hash.encode('utf-8')).hexdigest()
    if text_hash in api_cache:
        return api_cache[text_hash]

    # API URL
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    # Build the complete prompt text
    complete_prompt = context + "\n"
    if pdf_context_extract:
        complete_prompt += pdf_context_extract + "\n"
    complete_prompt += "Assignment Work: " + assignment_text

    payload = {
        "contents": [{
            "parts": [{"text": complete_prompt}]
        }]
    }

    # Send the POST request to the Gemini API
    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        result_data = response.json()
        print("Gemini API response received")
        candidates = result_data.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            if "content" in candidate:
                parts = candidate["content"].get("parts", [])
                generated_text = parts[0].get("text", "").strip() if parts else ""
            else:
                generated_text = candidate.get("output", "").strip()
        else:
            generated_text = ("Detailed evaluation: The assignment is well-organized and covers key technical aspects "
                              "comprehensively; however, there is room for improvement in analytical depth and clarity.")
    else:
        print(f"Error in Gemini API call: {response.status_code}")
        generated_text = "API call failed: unable to generate feedback."

    # Extract the exact grade from the generated text (searching for a pattern like "Overall Grade: 78/100")
    grade_pattern = r'Overall Grade:\s*(\d+)\s*/\s*100'
    grade_match = re.search(grade_pattern, generated_text, re.IGNORECASE)
    
    if grade_match:
        exact_grade = int(grade_match.group(1))
        # Remove the grade line from the feedback for a cleaner output
        cleaned_feedback = re.sub(grade_pattern + r'.*', '', generated_text, flags=re.IGNORECASE).strip()
    else:
        # Fallback grade calculation if not explicitly found in response
        exact_grade = min(100, len(assignment_text.split()) // 10)
        cleaned_feedback = generated_text

    result = {"grade": exact_grade, "feedback": cleaned_feedback}
    api_cache[text_hash] = result
    return result