# api.py

import os
import json
import requests
from requests_oauthlib import OAuth2Session

# --- Configuration ---
CLIENT_ID = "8125185E4CF74838A4269973EE475E7A"
CLIENT_SECRET = "emoGiUHsdOUYI3QVDppe_PUcjO2fgv8EiLkL1rKZkOjLm-kT"
REDIRECT_URI = "http://localhost:5000/callback"
#TOKEN_FILE = "xero_tokens.json"
TOKEN_FILE = "/home/ubuntu/webhook_magic/XeroInvoiceImport/xero_tokens.json"  # Path where tokens are saved
SCOPE = [
    "openid",
    "profile",
    "email",
    "payroll.employees",
    "payroll.timesheets",
    "payroll.settings",
]

# --- Xero API Endpoints ---
BASE_URL = "https://api.xero.com/api.xro/2.0"
PAYROLL_AU_URL = "https://api.xero.com/payroll.xro/1.0"
AUTHORIZATION_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"


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
        """Loads token from file."""
        try:
            with open(self.token_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_token(self, token):
        """Saves token to file."""
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

    def refresh_token(self):
        """Refreshes the access token."""
        try:
            print("Refreshing access token...")
            self.token = self.oauth.refresh_token(TOKEN_URL, client_id=self.client_id, client_secret=self.client_secret)
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
        """Makes a GET request to the Xero API."""
        if not self.token:
            raise ValueError("No token available. Please ensure you have provided valid tokens.")
            
        headers = {
            "Authorization": f"Bearer {self.token['access_token']}",
            "Xero-Tenant-Id": self.get_tenant_id(),
            "Accept": "application/json",
        }
        
        url = f"{PAYROLL_AU_URL}/{endpoint}"
        #print(f"Making GET request to: {url}")
        #print(f"Headers: {headers}")
        
        try:
            response = self.oauth.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            #print(f"Response status: {response.status_code}")
            #print(f"Response data: {json.dumps(data, indent=2)}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error response: {e.response.text}")
            raise

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
def create_xero_client(initial_token=None, tenant_id=None):
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
    xero_api_client = create_xero_client()
except ValueError:
    # Don't create the client if no token is available
    pass
