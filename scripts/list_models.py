#!/usr/bin/env python3
"""List available Gemini models via API."""

import os
from google import genai

# Set API key from .env
API_KEY = "AIzaSyCCVgN9zgPrIL6hUYrBE_ZlnNGm9SGHwDU"
os.environ['GOOGLE_API_KEY'] = API_KEY

print("=" * 60)
print("Available Gemini Models via API")
print("=" * 60)

try:
    client = genai.Client(api_key=API_KEY)

    # List all models
    models = client.models.list()

    print("\nAll Available Models:")
    print("-" * 60)
    for model in models:
        print(f"\nName: {model.name}")
        if hasattr(model, 'display_name'):
            print(f"Display Name: {model.display_name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"Supported Methods: {model.supported_generation_methods}")

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
