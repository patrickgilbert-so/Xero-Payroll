#!/usr/bin/env python3
"""
Authorization script to get fresh Xero Payroll API tokens.
Run this locally, then copy the generated token file to production.
"""

import os
import json
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from requests_oauthlib import OAuth2Session

# Allow http for local development (required for localhost callback)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Configuration
CLIENT_ID = "8125185E4CF74838A4269973EE475E7A"
CLIENT_SECRET = "emoGiUHsdOUYI3QVDppe_PUcjO2fgv8EiLkL1rKZkOjLm-kT"
REDIRECT_URI = "http://localhost:5000/callback"

AUTHORIZATION_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"

SCOPE = [
    "openid",
    "profile",
    "email",
    "accounting.transactions",
    "offline_access",
    "payroll.employees",
    "payroll.timesheets",
    "payroll.settings",
]

def authorize():
    """
    Perform OAuth2 authorization flow to get fresh tokens.
    """
    print("=" * 70)
    print("XERO PAYROLL API - AUTHORIZATION")
    print("=" * 70)
    print()
    print("This will open your browser to authorize the Xero Payroll API access.")
    print("After you authorize, you'll be redirected to http://localhost:5000/callback")
    print()
    
    # Create OAuth2 session with compliance_hook to ignore scope changes
    xero = OAuth2Session(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )
    
    # Generate authorization URL
    authorization_url, state = xero.authorization_url(AUTHORIZATION_URL)
    
    print(f"Authorization URL:")
    print(f"{authorization_url}")
    print()
    print("Opening your browser...")
    webbrowser.open(authorization_url)
    
    # Get authorization code from user
    print()
    print("After you authorize, Xero will redirect you to a URL like:")
    print("http://localhost:5000/callback?code=XXXX&state=YYYY")
    print()
    
    authorization_response = input("Paste the full URL you were redirected to: ").strip()
    
    # Exchange authorization code for tokens
    print()
    print("Exchanging authorization code for tokens...")
    
    try:
        token = xero.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            authorization_response=authorization_response
        )
    except Exception as e:
        # If scope validation fails but we have a token, try extracting it
        print(f"Warning during token fetch: {e}")
        print("Attempting to extract token directly...")
        
        # Extract code from authorization response URL
        parsed = urlparse(authorization_response)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        
        if not code:
            print("Error: Could not extract authorization code from URL")
            raise
        
        # Make direct request to token endpoint
        token_request = requests.post(
            TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }
        )
        
        if token_request.status_code == 200:
            token = token_request.json()
            print("✓ Token obtained successfully!")
        else:
            print(f"Error: {token_request.status_code}")
            print(f"Response: {token_request.text}")
            raise Exception(f"Failed to get token: {token_request.text}")
    
    # Save token to file
    token_file = os.path.join(os.path.dirname(__file__), "xero_tokens.json")
    
    with open(token_file, "w") as f:
        json.dump(token, f, indent=2)
    
    print()
    print("=" * 70)
    print("✓ Authorization successful!")
    print("=" * 70)
    print(f"Token saved to: {token_file}")
    print()
    print("Token details:")
    print(f"  - Access Token: {token.get('access_token', '')[:20]}...")
    print(f"  - Refresh Token: {token.get('refresh_token', '')[:20]}...")
    print(f"  - Expires in: {token.get('expires_in')} seconds")
    print()
    print("Next steps:")
    print("1. Verify the token works locally by running a test query")
    print("2. Copy xero_tokens.json to production server:")
    print("   scp xero_tokens.json ubuntu@YOUR_SERVER:/home/ubuntu/webhook_magic/Xero-Payroll/")
    print("3. Set permissions: chmod 666 /home/ubuntu/webhook_magic/Xero-Payroll/xero_tokens.json")
    print()

if __name__ == "__main__":
    authorize()
