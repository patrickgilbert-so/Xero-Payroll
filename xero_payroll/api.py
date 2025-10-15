# g:\Users\gilbe\PycharmProjects\Xero Payroll\xero_payroll\api.py

import os
import requests
from requests_oauthlib import OAuth2Session

# --- Configuration ---
# It's recommended to use environment variables for sensitive data.
# You can also use a configuration file (e.g., config.ini or .env).
CLIENT_ID = os.environ.get("XERO_CLIENT_ID")
CLIENT_SECRET = os.environ.get("XERO_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("XERO_REDIRECT_URI", "http://localhost:8080/callback")
SCOPE = [
    "openid",
    "profile",
    "email",
    "payroll.employees",
    "payroll.leaveapplications",
    "payroll.settings",
]

# --- Xero API Endpoints ---
BASE_URL = "https://api.xero.com/api.xro/2.0"
PAYROLL_AU_URL = "https://api.xero.com/payroll.xro/1.0"
AUTHORIZATION_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"


class XeroAPI:
    """A wrapper for the Xero API."""

    def __init__(self, client_id, client_secret, redirect_uri, scope):
        """Initializes the XeroAPI client."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.token = None
        self.tenant_id = None
        self.oauth = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri, scope=self.scope)

    def get_authorization_url(self):
        """Generates the authorization URL for the user to grant access."""
        return self.oauth.authorization_url(AUTHORIZATION_URL)

    def fetch_token(self, authorization_response):
        """Fetches the access token after the user has authorized the application."""
        self.token = self.oauth.fetch_token(
            TOKEN_URL,
            authorization_response=authorization_response,
            client_secret=self.client_secret,
        )
        return self.token

    def refresh_token(self):
        """Refreshes the access token."""
        self.token = self.oauth.refresh_token(TOKEN_URL, client_id=self.client_id, client_secret=self.client_secret)
        return self.token

    def get_tenant_id(self):
        """Retrieves the tenant ID required for API calls."""
        if not self.tenant_id:
            response = self.oauth.get("https://api.xero.com/connections")
            response.raise_for_status()
            self.tenant_id = response.json()[0]["tenantId"]
        return self.tenant_id

    def get(self, endpoint, params=None):
        """Makes a GET request to the Xero API."""
        headers = {
            "Authorization": f"Bearer {self.token['access_token']}",
            "Xero-Tenant-Id": self.get_tenant_id(),
            "Accept": "application/json",
        }
        response = self.oauth.get(f"{PAYROLL_AU_URL}/{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, data):
        """Makes a POST request to the Xero API."""
        headers = {
            "Authorization": f"Bearer {self.token['access_token']}",
            "Xero-Tenant-Id": self.get_tenant_id(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = self.oauth.post(f"{PAYROLL_AU_URL}/{endpoint}", headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    def put(self, endpoint, data):
        """Makes a PUT request to the Xero API."""
        headers = {
            "Authorization": f"Bearer {self.token['access_token']}",
            "Xero-Tenant-Id": self.get_tenant_id(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = self.oauth.put(f"{PAYROLL_AU_URL}/{endpoint}", headers=headers, json=data)
        response.raise_for_status()
        return response.json()


# --- Singleton Instance ---
# This makes it easy to use the same API client across the application.
xero_api_client = XeroAPI(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)
