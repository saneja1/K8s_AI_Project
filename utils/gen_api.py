import os
import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def generate_content(prompt_text, api_key=None, max_tokens=256, temperature=0.2):
    """Call the Google v1beta generateContent endpoint for gemini-2.0-flash."""
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
    }
    data = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }

    resp = requests.post(API_URL, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()