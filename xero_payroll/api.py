# api.py
import time
import os
import json
import requests
from requests_oauthlib import OAuth2Session
import pytz

# --- Configuration ---
CLIENT_ID = "4660E56A39F34A2C8E413794795D48A8"
CLIENT_SECRET = "RPC7BlkkMpyttd_aD64lDayKwiGePvOmS1MdxagXZqrD9QP7"
REDIRECT_URI = "http://localhost:5000/callback"

# Set TOKEN_FILE based on environment (production vs development)
if os.path.exists("/home/ubuntu/webhook_magic"):
    # Production: Ubuntu server - separate token file for Payroll API (different scopes than Invoicing)
    TOKEN_FILE = "/home/ubuntu/webhook_magic/Xero-Payroll/xero_tokens.json"
else:
    # Development: Local Windows machine
    TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "xero_tokens.json")

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

# --- Xero API Endpoints ---
BASE_URL = "https://api.xero.com/api.xro/2.0"
PAYROLL_AU_URL = "https://api.xero.com/payroll.xro/1.0"
AUTHORIZATION_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"

tenant_id = "993a65df-7298-40d2-8cdd-ca4a71f09e26"

class XeroAPI:
    """A wrapper for the Xero API."""

    def __init__(self, client_id, client_secret, token_file, initial_token=None, tenant_id=None):
        """
        Initializes the XeroAPI client.
        
        Args:
            client_id (str): The Xero API client ID
            client_secret (str): The Xero API client secret
            token_file (str): Path to the file where tokens will be stored
            initial_token (dict, optional): Initial token dictionary containing access_token and refresh_token
            tenant_id (str, optional): The Xero tenant ID. If not provided, will be fetched from the API
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file
        self.tenant_id = tenant_id
        
        # Try to load existing token from file first
        self.token = self.load_token()
        
        # If no token in file and initial token provided, use and save it
        if not self.token and initial_token:
            self.token = initial_token
            self.save_token(initial_token)
            
        if not self.token:
            raise ValueError("No token available. Please provide an initial token.")
        
        # Check if token is expired and refresh if needed
        import time
        if self.token.get("expires_at") and self.token.get("expires_at") < time.time():
            print(f"Token is expired (expires_at: {self.token.get('expires_at')}, now: {time.time()}), attempting refresh...")
            try:
                self.token = self._refresh_token_internal()
            except Exception as e:
                print(f"Warning: Token refresh failed, but will attempt to use existing token anyway")
                print(f"If API calls fail, you'll need to re-authorize the application")
                # Don't raise here - let the OAuth2Session handle auto-refresh on next request
            
        auto_refresh_kwargs = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        self.oauth = OAuth2Session(
            self.client_id,
            token=self.token,
            auto_refresh_url=TOKEN_URL,
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=self.save_token,
        )

    def load_token(self):
        try:
            with open(self.token_file, "r") as f:
                tok = json.load(f)
            # ensure expires_at exists if only expires_in is present
            if "expires_at" not in tok and "expires_in" in tok:
                tok["expires_at"] = int(time.time()) + int(tok["expires_in"])
            return tok
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def save_token(self, token):
        # normalise expires_at for future checks
        if "expires_at" not in token and "expires_in" in token:
            token["expires_at"] = int(time.time()) + int(token["expires_in"])
        with open(self.token_file, "w") as f:
            json.dump(token, f)
        self.token = token

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
        self.save_token(self.token)
        return self.token

    def _refresh_token_internal(self):
        """Internal method to refresh token before OAuth session is fully set up."""
        try:
            import requests
            print(f"Attempting to refresh token with refresh_token: {self.token.get('refresh_token', 'MISSING')[:20]}...")
            response = requests.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},  # add this
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.token.get("refresh_token"),
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30,
            )
            response.raise_for_status()
            new_token = response.json()
            if "expires_at" not in new_token and "expires_in" in new_token:
                new_token["expires_at"] = int(time.time()) + int(new_token["expires_in"])
            self.save_token(new_token)
            return new_token
        except Exception as e:
            print(f"Failed to refresh token during initialization: {e}")
            raise

    def refresh_token(self):
        """Refreshes the access token."""
        try:
            print("Refreshing access token...")
            self.token = self.oauth.refresh_token(
                TOKEN_URL, client_id=self.client_id, client_secret=self.client_secret
            )
            if "expires_at" not in self.token and "expires_in" in self.token:
                self.token["expires_at"] = int(time.time()) + int(self.token["expires_in"])
            self.save_token(self.token)
            print("Token refreshed successfully")
            
            # Check connections after refresh
            connections = self.oauth.get("https://api.xero.com/connections").json()
            if connections:
                print(f"Connected to {len(connections)} Xero organization(s)")
                for conn in connections:
                    print(f"- {conn.get('tenantName', 'Unknown')} ({conn['tenantId']})")
            else:
                print("Warning: No Xero organizations connected. Please authorize this application to at least one Xero organization.")
            
            return self.token
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            raise

    def get_tenant_id(self):
        """Retrieves the tenant ID required for API calls."""
        return "993a65df-7298-40d2-8cdd-ca4a71f09e26"
        if not self.tenant_id:
            try:
                response = self.oauth.get("https://api.xero.com/connections")
                response.raise_for_status()
                connections = response.json()
                
                if not connections:
                    raise ValueError("No Xero organizations found. Please ensure this application has been authorized to at least one Xero organization.")
                
                print(f"Found {len(connections)} Xero organization(s)")
                self.tenant_id = connections[0]["tenantId"]
                print(f"Using organization with tenant ID: {self.tenant_id}")
            except Exception as e:
                print(f"Error getting tenant ID: {str(e)}")
                print("\nAPI Response Content:")
                try:
                    print(response.content.decode())
                except:
                    print("Could not decode response content")
                raise
        return self.tenant_id

    def get(self, endpoint, params=None):
        if not self.token:
            raise ValueError("No token available.")
        headers = {
            "xero-tenant-id": self.get_tenant_id(),
            "Accept": "application/json",
        }
        url = f"{PAYROLL_AU_URL}/{endpoint}"
        r = self.oauth.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 401:
            # token just expired or was revoked; refresh and retry once
            try:
                print(f"[Xero] 401 body: {getattr(r, 'text', '')}")
            except Exception:
                pass
            self.refresh_token()
            r = self.oauth.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def post(self, endpoint, data):
        headers = {
            "xero-tenant-id": self.get_tenant_id(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        r = self.oauth.post(f"{PAYROLL_AU_URL}/{endpoint}", headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()

    # --- replace your put() with this ---
    def put(self, endpoint, data):
        headers = {
            "xero-tenant-id": self.get_tenant_id(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        r = self.oauth.put(f"{PAYROLL_AU_URL}/{endpoint}", headers=headers, json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def list_employees(self):
        """
        Retrieves a list of all employees from Xero Payroll.
        
        Returns:
            list: A list of dictionaries containing employee information with fields:
                - EmployeeID
                - FirstName
                - LastName
                - Status (Active/Terminated)
                - Email (if available)
        """
        print("\nAttempting to list employees...")
        
        response = self.get("Employees")
        #print("\nFull API Response:")
        #print(json.dumps(response, indent=2))
        
        employees = response.get("Employees", [])  # Note: Changed to match Xero's response structure
        
        # Format the response to include only necessary information
        employee_list = []
        for employee in employees:
            employee_info = {
                "EmployeeID": employee.get("EmployeeID"),
                "FirstName": employee.get("FirstName"),
                "LastName": employee.get("LastName"),
                "Status": employee.get("Status"),
                "Email": employee.get("Email")
            }
            employee_list.append(employee_info)
            
        return employee_list


# Function to create the API client instance
def create_xero_client(initial_token=None, tenant_id="993a65df-7298-40d2-8cdd-ca4a71f09e26"):
    """
    Creates a new XeroAPI client instance.
    
    Args:
        initial_token (dict, optional): Initial token dictionary containing access_token and refresh_token
        tenant_id (str, optional): The Xero tenant ID
    
    Returns:
        XeroAPI: A configured XeroAPI client instance
    """
    return XeroAPI(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_file=TOKEN_FILE,
        initial_token=initial_token,
        tenant_id=tenant_id
    )

# Default instance - will try to load token from file
xero_api_client = None
try:
    print(f"Attempting to initialize Xero API client from: {TOKEN_FILE}")
    print(f"Token file exists: {os.path.exists(TOKEN_FILE)}")
    xero_api_client = create_xero_client()
    print(f"✓ Xero API client initialized successfully")
except ValueError as e:
    print(f"❌ ValueError: Xero API client not initialized - {e}")
    print(f"Token file location: {TOKEN_FILE}")
    print(f"Token file exists: {os.path.exists(TOKEN_FILE)}")
except Exception as e:
    print(f"❌ Error initializing Xero API client: {e}")
    print(f"Token file location: {TOKEN_FILE}")
    print(f"Token file exists: {os.path.exists(TOKEN_FILE)}")
    import traceback
    traceback.print_exc()
