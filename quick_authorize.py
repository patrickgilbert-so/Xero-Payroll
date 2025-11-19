#!/usr/bin/env python3
"""
Quick authorization script - just exchange a code for tokens.
Usage: python quick_authorize.py <authorization_code>
"""

import sys
import json
import requests
from urllib.parse import urlparse, parse_qs

# Configuration
CLIENT_ID = "8125185E4CF74838A4269973EE475E7A"
CLIENT_SECRET = "emoGiUHsdOUYI3QVDppe_PUcjO2fgv8EiLkL1rKZkOjLm-kT"
REDIRECT_URI = "http://localhost:5000/callback"
TOKEN_URL = "https://identity.xero.com/connect/token"
TOKEN_FILE = "xero_tokens.json"

def exchange_code_for_token(code):
    """Exchange authorization code for tokens."""
    print(f"Exchanging code for tokens...")
    print(f"Code: {code[:20]}...")
    
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
        
        # Save to file
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token, f, indent=2)
        
        print()
        print("=" * 70)
        print("✓ SUCCESS! Token obtained and saved to xero_tokens.json")
        print("=" * 70)
        print()
        print("Token details:")
        print(f"  Access Token: {token.get('access_token', '')[:30]}...")
        print(f"  Refresh Token: {token.get('refresh_token', '')[:30]}...")
        print(f"  Expires in: {token.get('expires_in')} seconds")
        print(f"  Token Type: {token.get('token_type')}")
        print()
        print("Next steps:")
        print("1. Test locally: python main.py")
        print("2. Copy to production:")
        print("   scp xero_tokens.json ubuntu@YOUR_SERVER:/home/ubuntu/webhook_magic/Xero-Payroll/")
        print("3. On production server:")
        print("   chmod 666 /home/ubuntu/webhook_magic/Xero-Payroll/xero_tokens.json")
        print()
        return True
    else:
        print(f"✗ Error: {token_request.status_code}")
        print(f"Response: {token_request.text}")
        return False

def extract_code_from_url(url):
    """Extract authorization code from redirect URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    code = params.get('code', [None])[0]
    return code

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Code passed as argument
        code = sys.argv[1]
    else:
        # Ask for full URL
        print("=" * 70)
        print("XERO PAYROLL API - QUICK TOKEN EXCHANGE")
        print("=" * 70)
        print()
        print("Authorization URL:")
        print("https://login.xero.com/identity/connect/authorize?response_type=code&client_id=8125185E4CF74838A4269973EE475E7A&redirect_uri=http%3A%2F%2Flocalhost%3A5000%2Fcallback&scope=openid%20profile%20email%20accounting.transactions%20offline_access%20payroll.employees%20payroll.timesheets%20payroll.settings")
        print()
        print("1. Open the URL above in your browser")
        print("2. Click 'Authorize'")
        print("3. You'll be redirected to http://localhost:5000/callback?code=...")
        print()
        
        url_or_code = input("Paste either the full redirect URL or just the authorization code: ").strip()
        
        if "?" in url_or_code:
            # Full URL provided
            code = extract_code_from_url(url_or_code)
        else:
            # Just the code
            code = url_or_code
    
    if code:
        exchange_code_for_token(code)
    else:
        print("Error: Could not extract authorization code")
        sys.exit(1)
