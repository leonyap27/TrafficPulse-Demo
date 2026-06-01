#!/usr/bin/env python3
"""Test script to diagnose Vertex AI access issues."""

import os
from google import genai

# Configuration
PROJECT_ID = "gcci01jzrxwxjc6zhzj5p5dfg0qg7q"
LOCATION = "us-central1"
MODEL = "gemini-1.5-flash-002"

print("=" * 60)
print("Vertex AI Gemini Access Test")
print("=" * 60)

# Test 1: Check environment
print("\n1. Environment Variables:")
print(f"   PROJECT_ID: {PROJECT_ID}")
print(f"   LOCATION: {LOCATION}")
print(f"   MODEL: {MODEL}")

# Test 2: Try to initialize client
print("\n2. Initializing Vertex AI client...")
try:
    os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'True'
    os.environ['GOOGLE_CLOUD_PROJECT'] = PROJECT_ID
    os.environ['GOOGLE_CLOUD_LOCATION'] = LOCATION

    client = genai.Client(vertexai=True)
    print("   ✓ Client initialized successfully")
except Exception as e:
    print(f"   ✗ Error initializing client: {e}")
    exit(1)

# Test 3: Try to list models
print("\n3. Attempting to list available models...")
try:
    # This will fail if we don't have access
    response = client.models.generate_content(
        model=MODEL,
        contents="Say 'Hello' if you can read this."
    )
    print(f"   ✓ Model access confirmed!")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ✗ Error accessing model: {e}")
    print("\n   Possible causes:")
    print("   - Vertex AI API not enabled")
    print("   - Model not available in your project/region")
    print("   - Insufficient permissions")
    print("   - Billing not enabled")
    print("\n   To fix:")
    print("   1. Enable Vertex AI API:")
    print(f"      gcloud services enable aiplatform.googleapis.com --project={PROJECT_ID}")
    print("   2. Check available models:")
    print(f"      gcloud ai models list --region={LOCATION} --project={PROJECT_ID}")

print("\n" + "=" * 60)
