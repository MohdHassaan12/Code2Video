import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set a dummy OpenRouter API key for the test client environment
# This is used by the app.py when running in a non-request context or if not passed in headers
os.environ["OPENROUTER_MODELS"] = "google/gemini-3.5-flash"

# Assuming the Flask app is running on http://127.0.0.1:5000
STEM_LAB_URL = "http://127.0.0.1:5000"

def run_generate_code_test():
    # A minimal valid storyboard for testing
    test_storyboard = {
        "topic": "Test Topic",
        "key_theorems": ["Theorem 1"],
        "style_profile": "minimalist",
        "aspect_ratio": "widescreen",
        "visual_storyboard": [
            {
                "scene_index": 1,
                "description": "Introduction to the topic",
                "elements": [
                    {
                        "id": "title_text",
                        "type": "text",
                        "content": "Introduction",
                        "position": [0.0, 2.0],
                        "entrance_animation": "FadeIn",
                        "exit_animation": "FadeOut",
                        "scale": 0.8,
                        "safe_zone_alignment": "to_edge(UP, buff=0.6)"
                    }
                ],
                "narration_cues": [
                    {"cue": "नमस्ते, आज हम एक नए विषय का परिचय देंगे।", "event": "FadeIn(title_text)"}
                ],
                "wait_time": 2.0
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "X-OpenRouter-API-Key": os.environ["OPENROUTER_API_KEY"]
    }

    response = requests.post(
        f"{STEM_LAB_URL}/api/generate_code",
        json={
            'storyboard': test_storyboard,
            'style': 'minimalist'
        },
        headers=headers
    )

    data = response.json()

    print("--- Test Generate Code Output ---")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Generated Code:")
        print(data.get('code'))
        print("\nScene Class:")
        print(data.get('scene_class'))
        print("\nValid:")
        print(data.get('valid'))
        print("\nValidation Error:")
        print(data.get('validation_error'))
    else:
        print("Error:")
        print(data.get('error'))

if __name__ == '__main__':
    run_generate_code_test()
