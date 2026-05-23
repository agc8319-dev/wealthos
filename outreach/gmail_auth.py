#!/usr/bin/env python3
"""
Gmail OAuth Setup — run this once on your local machine to authorize
Gmail access. Generates gmail_token.json which the daily script uses.

Prerequisites:
  1. Go to console.cloud.google.com → New Project
  2. Enable the Gmail API
  3. Create OAuth 2.0 credentials (Desktop App)
  4. Download the JSON and save as outreach/gmail_credentials.json

Usage:
  python outreach/gmail_auth.py
"""

import os
import sys
import json

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
except ImportError:
    print("ERROR: google-auth-oauthlib not installed.")
    print("Run: pip install -r outreach/requirements.txt")
    sys.exit(1)

SCOPES           = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_FILE = os.environ.get("GMAIL_CREDENTIALS_FILE", "outreach/gmail_credentials.json")
TOKEN_FILE       = os.environ.get("GMAIL_TOKEN_FILE",       "outreach/gmail_token.json")


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: credentials file not found at {CREDENTIALS_FILE}")
        print()
        print("Steps to get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project, enable Gmail API")
        print("  3. APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop App)")
        print(f"  4. Download the JSON and save it as: {CREDENTIALS_FILE}")
        sys.exit(1)

    print("Opening browser for Gmail authorization...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\nAuthorization complete. Token saved to: {TOKEN_FILE}")
    print()
    print("For GitHub Actions, add the token as a secret:")
    print("  Secret name: GMAIL_TOKEN")
    print("  Secret value: (contents of the token file below)")
    print()
    with open(TOKEN_FILE) as f:
        data = json.load(f)
    print(f"  client_id:     {data.get('client_id', '')[:40]}...")
    print(f"  refresh_token: {str(data.get('refresh_token', ''))[:20]}...")


if __name__ == "__main__":
    main()
