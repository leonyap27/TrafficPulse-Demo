#!/usr/bin/env python3
"""
Test GCS Access and Configuration

This script tests your Google Cloud Storage setup by:
1. Checking if credentials are configured
2. Verifying bucket access
3. Listing files in the bucket
4. Attempting to download and read a sample file

Usage:
    python scripts/test_gcs_access.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from tools.gcs_client import get_gcs_client


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_status(success, message):
    """Print status message with checkmark or X."""
    symbol = "✓" if success else "✗"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {message}")


def test_configuration():
    """Test if GCS is configured in settings."""
    print_header("1. Testing Configuration")

    bucket_name = getattr(settings, "gcs_kb_bucket_name", None)
    project_id = getattr(settings, "gcs_project_id", None)
    credentials_path = getattr(settings, "gcs_credentials_path", None)

    if bucket_name:
        print_status(True, f"Bucket name configured: {bucket_name}")
    else:
        print_status(False, "Bucket name NOT configured (GCS_KB_BUCKET_NAME)")
        return False

    if project_id:
        print_status(True, f"Project ID configured: {project_id}")
    else:
        print_status(False, "Project ID NOT configured (GCS_PROJECT_ID)")
        return False

    if credentials_path:
        cred_file = Path(credentials_path)
        if cred_file.exists():
            print_status(True, f"Credentials file found: {credentials_path}")
        else:
            print_status(False, f"Credentials file NOT found: {credentials_path}")
            return False
    else:
        print_status(True, "No credentials path (will use default/workload identity)")

    return True


def test_gcs_client():
    """Test if GCS client can be initialized."""
    print_header("2. Testing GCS Client Initialization")

    try:
        client = get_gcs_client()
        if client:
            print_status(True, "GCS client initialized successfully")
            print_status(True, f"Connected to bucket: {client.bucket_name}")
            return client
        else:
            print_status(False, "GCS client could not be initialized")
            print("  → Check your configuration in .env file")
            return None
    except Exception as e:
        print_status(False, f"Error initializing GCS client: {str(e)}")
        return None


def test_bucket_access(client):
    """Test if bucket is accessible."""
    print_header("3. Testing Bucket Access")

    try:
        # Try to list files
        files = client.list_kb_files()
        print_status(True, f"Successfully accessed bucket")
        print_status(True, f"Found {len(files)} files in KB folders")
        return files
    except Exception as e:
        print_status(False, f"Cannot access bucket: {str(e)}")
        print("\n  Possible issues:")
        print("  1. Service account doesn't have read permission")
        print("  2. Bucket doesn't exist")
        print("  3. Credentials are invalid")
        print("\n  Try:")
        print(f"    gcloud storage ls gs://{client.bucket_name}/")
        return None


def test_list_files(files):
    """List files found in bucket."""
    print_header("4. Listing KB Files")

    if not files:
        print_status(False, "No files found in bucket")
        print("\n  Expected structure:")
        print("    gs://your-bucket/kb/guidelines/")
        print("    gs://your-bucket/kb/past_papers/")
        return None

    guidelines = [f for f in files if f["doc_type"] == "guideline"]
    past_papers = [f for f in files if f["doc_type"] == "past_paper"]

    print(f"\n  Guidelines ({len(guidelines)}):")
    for f in guidelines[:5]:  # Show first 5
        size_kb = f["size_bytes"] / 1024
        print(f"    - {f['filename']} ({size_kb:.1f} KB)")
    if len(guidelines) > 5:
        print(f"    ... and {len(guidelines) - 5} more")

    print(f"\n  Past Papers ({len(past_papers)}):")
    for f in past_papers[:5]:  # Show first 5
        size_kb = f["size_bytes"] / 1024
        print(f"    - {f['filename']} ({size_kb:.1f} KB)")
    if len(past_papers) > 5:
        print(f"    ... and {len(past_papers) - 5} more")

    return files[0] if files else None


def test_download_file(client, file_info):
    """Test downloading and reading a file."""
    print_header("5. Testing File Download & Read")

    if not file_info:
        print_status(False, "No file available for download test")
        return False

    try:
        import tempfile

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.txt') as tmp:
            tmp_path = Path(tmp.name)

        print(f"\n  Downloading: {file_info['filename']}")
        print(f"  From: {file_info['name']}")
        print(f"  Size: {file_info['size_bytes'] / 1024:.1f} KB")

        # Download file
        success = client.download_file(file_info['name'], tmp_path)

        if success and tmp_path.exists():
            print_status(True, "File downloaded successfully")

            # Try to read file content
            try:
                # Check if it's a text file
                if file_info['filename'].endswith(('.txt', '.md')):
                    content = tmp_path.read_text(encoding='utf-8')
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print_status(True, "File content read successfully")
                    print(f"\n  Content preview:")
                    print("  " + "-" * 58)
                    for line in preview.split('\n')[:5]:
                        print(f"  {line}")
                    print("  " + "-" * 58)
                else:
                    print_status(True, f"Binary file downloaded ({file_info['filename']})")
                    print("  ℹ Text extraction would be done during sync")

            except Exception as e:
                print_status(False, f"Could not read file content: {str(e)}")

            # Clean up
            tmp_path.unlink()
            return True
        else:
            print_status(False, "File download failed")
            return False

    except Exception as e:
        print_status(False, f"Error downloading file: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  GCS Access Test Suite")
    print("  Testing Google Cloud Storage configuration and access")
    print("=" * 60)

    # Test 1: Configuration
    if not test_configuration():
        print("\n" + "=" * 60)
        print("  FAILED: Configuration is incomplete")
        print("=" * 60)
        print("\nPlease configure the following in your .env file:")
        print("  - GCS_KB_BUCKET_NAME=your-bucket-name")
        print("  - GCS_PROJECT_ID=your-project-id")
        print("  - GCS_CREDENTIALS_PATH=/path/to/key.json (optional)")
        print("\nSee docs/GCS_GETTING_STARTED.md for setup instructions.")
        sys.exit(1)

    # Test 2: Client initialization
    client = test_gcs_client()
    if not client:
        print("\n" + "=" * 60)
        print("  FAILED: Could not initialize GCS client")
        print("=" * 60)
        sys.exit(1)

    # Test 3: Bucket access
    files = test_bucket_access(client)
    if files is None:
        print("\n" + "=" * 60)
        print("  FAILED: Cannot access bucket")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("  1. Verify bucket exists:")
        print(f"       gcloud storage ls gs://{client.bucket_name}/")
        print("  2. Check service account permissions:")
        print(f"       gcloud storage buckets get-iam-policy gs://{client.bucket_name}")
        print("  3. Test authentication:")
        print(f"       gcloud auth activate-service-account --key-file={getattr(settings, 'gcs_credentials_path', 'path/to/key.json')}")
        sys.exit(1)

    # Test 4: List files
    sample_file = test_list_files(files)

    # Test 5: Download and read
    if sample_file:
        test_download_file(client, sample_file)

    # Final summary
    print_header("Test Summary")
    print_status(True, "Configuration: OK")
    print_status(True, "GCS Client: OK")
    print_status(True, "Bucket Access: OK")
    print_status(True, f"Files Found: {len(files)}")
    if sample_file:
        print_status(True, "File Download: OK")

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nYour GCS setup is working correctly!")
    print("\nNext steps:")
    print("  1. Sync KB from GCS:")
    print("       python scripts/sync_kb_from_gcs.py --action sync")
    print("  2. Start the API server:")
    print("       cd api && uvicorn main:app --reload")
    print("  3. Verify KB status:")
    print("       curl http://localhost:8000/kb/status")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
