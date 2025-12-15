# main.py

import sys
import json
import logging
from datetime import date, timedelta
from xero_payroll.api import xero_api_client, create_xero_client
from xero_payroll.leave import (
    get_employee_leave_balance,
    get_future_scheduled_leave,
    get_leave_summary,
    predict_leave_balance,
    create_leave_request,
    approve_leave_request,
    reject_leave_request,
    LEAVE_TYPES,
)
import pytz
from datetime import datetime
import requests
import time
from urllib.parse import urljoin
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from html import escape
import re
import ast
import html
from typing import Any, Dict, List, Optional

TAG_RE = re.compile(r"<[^>]+>")


# Set up logging - both console and file
import os
#log_file = os.path.join(os.path.dirname(__file__), "xero_payroll_webhook.log")
# Setup shared logging
logging.basicConfig(
    #filename="/home/ubuntu/webhook_magic/webhook.log",
    filename="webhook.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: [Xero_Payroll] %(message)s"
)
logger = logging.getLogger(__name__)

DATE_FROM = str(20160101)
DATE_TO = str(20250331)
DATE_FROM = "2025, 06, 29"
DATE_TO = "2025, 06, 31"

JOB_HISTORY_GLOBAL=''
job_history=''
TARGET_PROJECT_NUMBER=''
checkduplicates = True #whether to create and check for duplicates - normally TRUE unless reimporting for a particular project
nonbillable_only = False #whether to only grab the nonbillable entries. Normally False.
skip_company_overheads = False #whether to skips UDEC-OH, UDEC-Leave, UDEC-Holding Phase projects

bot_task_id=None
status_automation_running="IEAF5D2JJMGMMY7W"
status_completed="IEAF5D2JJMGMMY6F"
status_error="IEAF5D2JJMGOQZP3"

# some important UDEC Wrike CIT_ID ids
wrike_invoice_lineitem_CIT_ID = 'IEAF5D2JPIAENQ7H'
wrike_invoices_folder_CIT_ID = 'IEAF5D2JPIABVA5X'
wrike_invoice_CIT_ID = 'IEAF5D2JPIABVAOP'

    # Define the IDs you want to extract
custom_field_ids = {
    "person_name": "IEAF5D2JJUAGXSTI",
    "target_date": "IEAF5D2JJUAJ2ZJG",
    "leave_type": "IEAF5D2JJUAJ2ZJJ",
    "job_history": "IEAF5D2JJUAIWT6G"
}  


# ========= CONFIG =========
WRIKE_CLIENT_ID     = os.getenv("WRIKE_CLIENT_ID",     "TmHomnYj")
WRIKE_CLIENT_SECRET = os.getenv("WRIKE_CLIENT_SECRET", "U4K3svn7hS8pPLPhzZkgjXvlMLknrPAn3pf4gaHJY81JVvdABhEHKgWvbCTCbj1D")


WRIKE_HOST_ROOT = "https://www.wrike.com"
#this is Wrike root

# this is Wrike API base for convenience
WRIKE_API_BASE = f"{WRIKE_HOST_ROOT}/api/v4"

# Where we persist tokens
WRIKE_TOKEN_PATH = Path(os.getenv("WRIKE_TOKEN_PATH", "../WRIKE_tokens.json"))
#WRIKE_TOKEN_PATH = "/home/ubuntu/webhook_magic/WRIKE_tokens.json"

# ========= TOKEN IO =========
def load_WRIKE_token():
    if WRIKE_TOKEN_PATH.exists():
        with WRIKE_TOKEN_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_WRIKE_token(tokens: dict):
    WRIKE_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WRIKE_TOKEN_PATH.open("w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

# ========= SESSION WITH RETRIES =========
def make_WRIKE_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "PUT", "POST", "DELETE", "PATCH"])
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    return s

WRIKE_session = make_WRIKE_session()



# ========= AUTH HELPERS =========
def WRIKE_auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}

def WRIKE_refresh_access_token(refresh_token: str) -> dict:
    if not (WRIKE_CLIENT_ID and WRIKE_CLIENT_SECRET and WRIKE_HOST_ROOT):
        raise RuntimeError(
            "Missing WRIKE_CLIENT_ID, WRIKE_CLIENT_SECRET, or WRIKE_HOST_ROOT. "
            "Set these env vars before attempting a refresh."
        )

    token_url = f"{WRIKE_HOST_ROOT}/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": WRIKE_CLIENT_ID,
        "client_secret": WRIKE_CLIENT_SECRET,
    }

    logging.info(f"[WRIKE_refresh_access_token] Refreshing at: {token_url}, {refresh_token}, {WRIKE_CLIENT_ID}, {WRIKE_CLIENT_SECRET}")
    try:
        resp = requests.post(token_url, data=data, timeout=15)
    except requests.RequestException as e:
        logging.error(f"[WRIKE_refresh_access_token] Network error refreshing token: {e}")
        raise

    if resp.status_code != 200:
        # Log safely (truncate body to avoid secrets; Wrike doesn't echo secrets back anyway)
        body = (resp.text or "")[:500]
        logging.error(f"[WRIKE_refresh_access_token] Refresh failed "
                      f"(status={resp.status_code}). Body: {body}")
        # Helpful hints for common causes
        if resp.status_code in (300, 301, 302, 303, 307, 308):
            logging.error("[WRIKE_refresh_access_token] Got a redirect. "
                          "Your WRIKE_HOST_ROOT is probably wrong. Use your regional host.")
        if resp.status_code == 400 and "invalid_grant" in body.lower():
            logging.error("[WRIKE_refresh_access_token] invalid_grant: refresh_token is invalid/expired "
                          "or does not belong to this client_id. Re-authorize to obtain a new pair.")
        resp.raise_for_status()

    tokens = resp.json()
    tokens = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token", refresh_token),
        "token_type": tokens.get("token_type", "bearer"),
        "expires_in": tokens.get("expires_in"),
        "obtained_at": int(time.time()),
    }
    save_WRIKE_token(tokens)
    logging.info("[WRIKE_refresh_access_token] Token refreshed and saved.")
    return tokens

# ========= CORE REQUEST (AUTO-REFRESH) =========
def WRIKE_request(
    method: str,
    path_or_url: str,
    *,
    params=None,
    json_body=None,
    data=None,
    allow_refresh=True,
):
    """
    Makes a Wrike API call, auto-refreshing the token on 401 once.
    `path_or_url` can be '/tasks/ID' or a full URL.
    """
    logging.debug(f"In WRIKE_request...")
    url = path_or_url if path_or_url.startswith("http") else urljoin(WRIKE_API_BASE + "/", path_or_url.lstrip("/"))

    logging.debug(f"Loading WRIKE token...")
    tokens = load_WRIKE_token()

    #headers = WRIKE_auth_headers(tokens["access_token"])
    logging.debug(f"creating WRIKE headers...")
    headers = WRIKE_auth_headers(tokens.get("access_token", ""))
    logging.debug(f"WRIKE headers = {headers}")

    resp = WRIKE_session.request(method, url, headers=headers, params=params, json=json_body, data=data)
    logging.debug(f"Request URL: {resp.request.method} {resp.request.url}")
    logging.debug(f"Status: {resp.status_code}")
    logging.debug(f"Headers: {dict(resp.headers)}")
    logging.debug(f"Location header: {resp.headers.get('Location')}")
    logging.debug(f"Body (first 500): {resp.text[:500]}")
    logging.debug(f"resp={resp}")
    logging.debug(f"Status: {resp.status_code}")
    logging.debug(f"Location header: {resp.headers.get('Location')}")
    # Refresh on 401
    if resp.status_code == 401 and allow_refresh:
        logging.info("Wrike access token likely expired. Refreshing…")
        if not tokens.get("refresh_token"):
            raise RuntimeError("No Wrike refresh_token found. Re-authorize to obtain one.")
        logging.debug("About to try to get refresh token…")
        tokens = WRIKE_refresh_access_token(tokens["refresh_token"])
        logging.debug("Getting auth headers…")
        headers = WRIKE_auth_headers(tokens["access_token"])
        logging.debug("trying request again…")
        resp = WRIKE_session.request(method, url, headers=headers, params=params, json=json_body, data=data)

    # Rate limit handling
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 5))
        logging.warning(f"Wrike rate limit hit (429). Retrying after {retry_after}s…")
        time.sleep(retry_after)
        resp = WRIKE_session.request(method, url, headers=headers, params=params, json=json_body, data=data)

    # Follow redirects if any
    if resp.status_code in (300, 301, 302, 303, 307, 308):
        loc = resp.headers.get("Location")
        if loc:
            logging.debug(f"Following Wrike redirect to {loc}")
            next_url = loc if loc.startswith("http") else urljoin(WRIKE_HOST_ROOT + "/", loc.lstrip("/"))
            resp = WRIKE_session.request(method, next_url, headers=headers, params=params, json=json_body, data=data)

    return resp

# ========= CONVENIENCE WRAPPERS =========
def WRIKE_get(path_or_url, **kw):    return WRIKE_request("GET", path_or_url, **kw)
def WRIKE_put(path_or_url, **kw):    return WRIKE_request("PUT", path_or_url, **kw)
def WRIKE_post(path_or_url, **kw):   return WRIKE_request("POST", path_or_url, **kw)
def WRIKE_patch(path_or_url, **kw):  return WRIKE_request("PATCH", path_or_url, **kw)
def WRIKE_delete(path_or_url, **kw): return WRIKE_request("DELETE", path_or_url, **kw)

def get_Wrike_Task(taskId):

    WRIKE_URL = (
        f'https://www.wrike.com/api/v4/tasks/{taskId}'
    )
    logging.info(f"[get_Wrike_Task] WRIKE_URL={WRIKE_URL}")
    response = WRIKE_request("GET",WRIKE_URL)

    #response = requests.get(WRIKE_URL, headers=wrike_headers, json=payload)
    # then need to return the created taskid

    if response.status_code != 200:
        logging.error(f"[get_Wrike_Task] Received status code {response.status_code}")
        root=None
    else:
        root = response.json()
        logging.debug(f"[get_Wrike_Task] json response (root)={root}")
        #if root.get('data') and len(root['data']) > 0:
        #    found_id = root['data'][0]['id']
        #else:
        #    found_id = None

    return root

def build_custom_field_index(custom_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Converts: [{'id': 'X', 'value': ...}, ...] into {'X': value, ...}
    """
    return {f.get("id"): f.get("value") for f in (custom_fields or []) if isinstance(f, dict) and f.get("id")}

def normalize_cf_value(value: Any, *, max_len: int = 1200, strip_html_tags: bool = True) -> str:
    """
    Make a custom field value human-readable for logging:
    - HTML unescape (&lt; &gt; &#x27; etc.)
    - Convert <br> to newline
    - Remove <pre> wrappers
    - Optionally strip remaining HTML tags
    - Try to pretty-print embedded dict/list strings (Python-literal style)
    """
    if value is None:
        return "None"

    # Convert non-strings to a readable string early
    if not isinstance(value, str):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)[:max_len]
        except Exception:
            return str(value)[:max_len]

    s = value

    # Unescape HTML entities first (turn &lt; into < etc.)
    s = html.unescape(s)

    # Normalize breaks and whitespace
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

    # Remove common wrappers but keep their content
    s = re.sub(r"</?pre[^>]*>", "", s, flags=re.IGNORECASE).strip()

    # Optional: strip any remaining HTML tags (e.g., <b>)
    if strip_html_tags:
        s = TAG_RE.sub("", s)

    s = s.strip()

    # Try to parse embedded Python-literal dict/list (your leave summary is like "{'employee_name': ...}")
    # This will also handle lists like "[{'id': '...', 'value': ...}]"
    parsed = None
    try:
        # Only attempt if it looks like a literal structure
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            parsed = ast.literal_eval(s)
    except Exception:
        parsed = None

    if parsed is not None:
        try:
            s = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            s = str(parsed)

    # Truncate for logs
    if len(s) > max_len:
        s = s[:max_len] + " …(truncated)"

    return s

def log_custom_fields_readable(
    logger,
    custom_fields: List[Dict[str, Any]],
    *,
    id_to_name: Optional[Dict[str, str]] = None,
    max_len: int = 1200,
) -> None:
    """
    Logs each custom field on its own line with readable formatting.
    """
    id_to_name = id_to_name or {}
    idx = build_custom_field_index(custom_fields)

    for fid, raw in idx.items():
        name = id_to_name.get(fid, "Unknown")
        pretty = normalize_cf_value(raw, max_len=max_len)
        logger.info(f"[custom_fields] {name} ({fid}) =\n{pretty}")



def wrike_text_cf_value(text: str) -> str:
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # IMPORTANT: <br> is not allowed in Text Custom Fields in Wrike.
    # Either remove it or convert to newline / wrap in <pre>.
    text = text.replace("<br>", "\n")

    # Optional but recommended: wrap in <pre> (allowed for text custom fields) and escape HTML
    # so your logs don't accidentally become interpreted markup.
    return f"<pre>{escape(text)}</pre>"

def handle_webhook_payload(payload):
    """
    Process webhook payload and return appropriate response.
    
    Args:
        payload (dict or list): The webhook payload containing event data
        
    Returns:
        dict: Response data containing processed information
    """
    job_summary=''

      # Define the IDs you want to extract
    custom_field_ids = {
        "person_name": "IEAF5D2JJUAGXSTI",
        "target_date": "IEAF5D2JJUAJ2ZJG",
        "leave_type": "IEAF5D2JJUAJ2ZJJ",
        "job_history": "IEAF5D2JJUAIWT6G"
    }  

    try:
        # Check if API client is initialized
        if not xero_api_client:
            raise ValueError("Xero API client not initialized. Token file may not exist or be invalid.")
        
        logger.info(f"Processing webhook payload: {payload}")
        
        # Handle array of events (extract first event)
        if isinstance(payload, list):
            if len(payload) == 0:
                raise ValueError("Empty payload list received")
            logger.info(f"Payload is a list, extracting first event from {len(payload)} events")
            payload = payload[0]
        
        # Get the event type and relevant data
        event_type = payload.get("status")
        if not event_type:
            raise ValueError("No status/eventType specified in payload")
            
        response_data = {"status": "success", "data": None}
        
        if event_type == "Idle":
            # No action needed for idle events
            logger.info("Received Idle event - no action taken")
            return response_data
        elif event_type == "Completed":
            # No action needed for completed events
            logger.info("Received Completed event - no action taken")
            return response_data
        elif event_type == "Automation Running":
            # No action needed for completed events
            logger.info("Received Automation Running event - no action taken")
            return response_data
        elif event_type == "Error":
            # No action needed for completed events
            logger.info("Received Error event - no action taken")
            return response_data

        else:
            response=get_Wrike_Task(bot_task_id)
            custom_fields = response['data'][0]['customFields']

            job_summary=f"Received Inputs:\n{custom_fields}"
            logging.info(f"🚀 [handle_webhook_payload] got custom fields {custom_fields}")

            # Build an index once
            cf_index = build_custom_field_index(custom_fields)

            def get_custom_field_value(field_id: str):
                return cf_index.get(field_id)
            # Helper to find value by ID
            #def get_custom_field_value(field_id):
            #    for field in custom_fields:
            #        if field['id'] == field_id:
            #            return field.get('value')
            #    return None


            job_history = get_custom_field_value(custom_field_ids["job_history"])
            person_name = get_custom_field_value(custom_field_ids["person_name"])
            target_date = get_custom_field_value(custom_field_ids["target_date"])
            leave_type= get_custom_field_value(custom_field_ids["leave_type"])
            JOB_HISTORY_GLOBAL=job_history

            # Optional: log the full set readably (recommended while debugging)
            log_custom_fields_readable(
                logging,
                custom_fields,
                id_to_name={
                    custom_field_ids["job_history"]: "Job History",
                    custom_field_ids["person_name"]: "Person Name",
                    custom_field_ids["target_date"]: "Target Date",
                    custom_field_ids["leave_type"]: "Leave Type",
                    # add others as you like
                },
                max_len=1500,
            )
            #logging.info(f"🚀 [handle_webhook_payload] extracted custom fields: person_name={person_name}, target_date={target_date}, leave_type={leave_type}, job_history={job_history}")
            # Also log the extracted values in readable form
            logging.info(
                "🚀 extracted custom fields: person_name=%s, target_date=%s, leave_type=%s, job_history=\n%s",
                normalize_cf_value(person_name, max_len=200),
                normalize_cf_value(target_date, max_len=200),
                normalize_cf_value(leave_type, max_len=200),
                normalize_cf_value(job_history, max_len=1500),
            )
            if event_type == "Get Leave Summary":

                
                # Handle leave summary request
                # Try to get employeeId from multiple possible locations
                employee_id = (
                    payload.get("employeeId") or 
                    payload.get("employee_id") or 
                    payload.get("customField:employeeId") or
                    "b5c4187a-1d2d-4712-8764-6bd01ef4af7d" # For testing purposes
                    #payload.get("taskId")  # Fallback to taskId if no employee ID
                )
                
                if not employee_id:
                    raise ValueError("No employeeId specified for leave summary request")
                    
                logger.info(f"Getting leave summary for employee: {employee_id}")
                job_summary=job_summary+f"\nProcessing Get Leave Summary for employee {employee_id}"
                #job_summary=wrike_text_cf_value(job_summary)
                bot_response=update_Wrike_bot(bot_task_id, status_automation_running, job_summary)
                summary = get_leave_summary(employee_id)
                response_data["data"] = summary
                job_summary=f"\n\n<b>Leave Summary:</b>\n{summary}"
                #job_summary=wrike_text_cf_value(job_summary)

                
                
            elif event_type == "Get Leave Balance":
                # Handle leave balance request

                # Try to get employeeId from multiple possible locations
                employee_id = (
                    payload.get("employeeId") or 
                    payload.get("employee_id") or 
                    payload.get("customField:employeeId") or
                    "b5c4187a-1d2d-4712-8764-6bd01ef4af7d" # For testing purposes
                    #payload.get("taskId")  # Fallback to taskId if no employee ID
                )
                
                if not employee_id:
                    raise ValueError("No employeeId specified for leave summary request")

                
                leave_type = payload.get("leaveType")
                if not leave_type:
                    logger.info("No leaveType specified for leave balance request - defaulting to annual leave")
                    leave_type = "Annual"
                if not employee_id or not leave_type:
                    raise ValueError("Missing employeeId or leaveType for leave balance request")
                    
                balance = get_employee_leave_balance(employee_id, leave_type)
                response_data["data"] = {"balance": balance}
                
            elif event_type == "Predict Leave Balance at Date":
                # Handle leave prediction request
                employee_id = (
                    payload.get("employeeId") or 
                    payload.get("employee_id") or 
                    payload.get("customField:employeeId") or
                    "b5c4187a-1d2d-4712-8764-6bd01ef4af7d" # For testing purposes
                    #payload.get("taskId")  # Fallback to taskId if no employee ID
                )

                leave_type = payload.get("leaveType")

                if not leave_type:
                    logger.info("No leaveType specified for leave balance request - defaulting to annual leave")
                    leave_type = "Annual"

                future_date = date.fromisoformat(payload.get("date")) if payload.get("date") else None

                if not future_date:
                    future_date= date.today() + timedelta(days=365)  # Default to 365 days in future
                
                if not all([employee_id, leave_type, future_date]):
                    raise ValueError("Missing required fields for leave prediction request")
                    
                predicted = predict_leave_balance(employee_id, leave_type, future_date)
                response_data["data"] = {"predicted_balance": predicted}
                
            elif event_type == "Get Future Scheduled Leave":
                # Handle future scheduled leave request
                employee_id = (
                    payload.get("employeeId") or 
                    payload.get("employee_id") or 
                    payload.get("customField:employeeId") or
                    "b5c4187a-1d2d-4712-8764-6bd01ef4af7d" # For testing purposes
                    #payload.get("taskId")  # Fallback to taskId if no employee ID
                )

                leave_type = payload.get("leaveType")
                if not leave_type:
                    logger.info("No leaveType specified for leave balance request - defaulting to annual leave")
                    leave_type = "Annual"
                
                if not employee_id or not leave_type:
                    raise ValueError("Missing employeeId or leaveType for future scheduled leave request")
                    
                scheduled_leave = get_future_scheduled_leave(employee_id, leave_type)
                response_data["data"] = {"scheduled_leave": scheduled_leave}
                
            elif event_type == "Get Xero Employee List":
                # Handle employee list request
                employees = xero_api_client.list_employees()
                response_data["data"] = {
                    "employees": [{
                        "id": emp["EmployeeID"],
                        "firstName": emp["FirstName"],
                        "lastName": emp["LastName"],
                        "status": emp["Status"],
                        "email": emp.get("Email", "N/A")
                    } for emp in employees]
                }
                
            else:
                bot_response=update_Wrike_bot(bot_task_id, status_error, f"Unsupported event type: {event_type}")
                raise ValueError(f"Unsupported event type: {event_type}")

        # update the bot task with status
        # Set Melbourne timezone

        bot_response=update_Wrike_bot(bot_task_id, status_completed, job_summary)

        return response_data
        
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}", exc_info=True)
        bot_response=update_Wrike_bot(bot_task_id, status_error, job_summary+f"\nError: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

def display_employee_list():
    """
    Retrieves and displays a list of all employees from Xero.
    """
    try:
        employees = xero_api_client.list_employees()
        print("\n=== Xero Employees ===")
        print("ID | Name | Status | Email")
        print("-" * 50)
        for emp in employees:
            name = f"{emp['FirstName']} {emp['LastName']}"
            print(f"{emp['EmployeeID']} | {name} | {emp['Status']} | {emp.get('Email', 'N/A')}")
        print("-" * 50)
        return employees
    except Exception as e:
        print(f"Error retrieving employee list: {e}")
        return []

def main():
    """
    Main function to demonstrate the Xero Payroll API integration.
    """
    global xero_api_client
    
    # Example of how to initialize with tokens
    if not xero_api_client:
        # You would normally get these values from your secure storage
        initial_token = {
            "access_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFDQUY4RTY2NzcyRDZEQzAyOEQ2NzI2RkQwMjYxNTgxNTcwRUZDMTkiLCJ0eXAiOiJKV1QiLCJ4NXQiOiJISy1PWm5jdGJjQW8xbkp2MENZVmdWY09fQmsifQ.eyJuYmYiOjE3NjE2MjU5NjMsImV4cCI6MTc2MTYyNzc2MywiaXNzIjoiaHR0cHM6Ly9pZGVudGl0eS54ZXJvLmNvbSIsImF1ZCI6Imh0dHBzOi8vaWRlbnRpdHkueGVyby5jb20vcmVzb3VyY2VzIiwiY2xpZW50X2lkIjoiODEyNTE4NUU0Q0Y3NDgzOEE0MjY5OTczRUU0NzVFN0EiLCJzdWIiOiIzZmYxMTAwMWE2NDI1NWZmYTk3MzEzY2RkNWMwODg4YSIsImF1dGhfdGltZSI6MTc2MTYyNTgyNywieGVyb191c2VyaWQiOiIyMzdmMmMxZC0wZTQ3LTQyNTgtOTdlMC1iMmNkNjEwNjc4ZTUiLCJnbG9iYWxfc2Vzc2lvbl9pZCI6IjNjOGZhYzM0Njg3MDQ3NDE4YTE4OGZmNTViODgwMjVhIiwic2lkIjoiM2M4ZmFjMzQ2ODcwNDc0MThhMTg4ZmY1NWI4ODAyNWEiLCJhdXRoZW50aWNhdGlvbl9ldmVudF9pZCI6ImI3YjRhZmE0LTgxMTEtNDMwNC1iMmU4LWU4OTlkMzQ0MDU4NiIsImp0aSI6IjhCNDUxNUFGM0YzNEZEMTRDMzJBMDVGMjg1Q0ZBMzVBIiwic2NvcGUiOlsiZW1haWwiLCJwcm9maWxlIiwib3BlbmlkIiwicGF5cm9sbC5lbXBsb3llZXMiLCJwYXlyb2xsLnRpbWVzaGVldHMiLCJhY2NvdW50aW5nLnRyYW5zYWN0aW9ucyIsInBheXJvbGwuc2V0dGluZ3MiLCJvZmZsaW5lX2FjY2VzcyJdLCJhbXIiOlsicHdkIl19.kqJ7RL-voJH9hC8KgumPbjiGtibdYQgbKqDNNKIvey1kkurfXVbUZL6BRThRKARnnYXAcdViU2oWG0v9VUB9-XrTkK6uPUa9vllapJ7_2ZNeX3m0ln0WAdag331rOYoZneKc-KrBSnTp1IGl3AskDmEnZc2TvGTasOrn20I4o7mTbpRroZnpqoEDeCgD4Ag9ULTQdxUPu_v_iKRwnRYAcbCNYfjzOJW-BslYOpBWY7cpnQLuZWbsJIJZ2sA5x-7AMox0WJAu1Xh98VYGzJJtFZr6kKWb8MVKjPUwZIQ9mtP3MYT8Ip7Q18qaScLO6k0MgKXxPbbskBXFn3RqAz-dEQ",
            "refresh_token": "P1DjU9MjTWVr6HIwzka4Ll4l_t5fBbiw4stl5iCPuXI",
            "token_type": "Bearer",
            "expires_in": 1800,  # 30 minutes
            "expires_at": 1735473600  # Unix timestamp when token expires
        }
        
        tenant_id = "993a65df-7298-40d2-8cdd-ca4a71f09e26"  # Optional, will be fetched if not provided
        
        try:
            xero_api_client = create_xero_client(initial_token, tenant_id)
            print("API client initialized successfully!")
        except Exception as e:
            print(f"Error initializing API client: {e}")
            return

    # --- Example Usage ---
    # Replace with a real EmployeeID from your Xero account.
    employee_id = "your_employee_id_here" 
    
    # Display list of employees
    print("\nRetrieving employee list...")
    employees = display_employee_list()
    
    if not employees:
        print("No employees found or error occurred.")
        return
    
    # Ask user to select an employee
    employee_id = input("\nEnter the Employee ID you want to work with (or press Enter to exit): ").strip()
    if not employee_id:
        return
        
    print(f"\n--- Operations for Employee: {employee_id} ---")

    # 1. Get leave balance for a specific category
    try:
        annual_leave_balance = get_employee_leave_balance(employee_id, "Annual")
        print(f"\nAnnual Leave Balance: {annual_leave_balance} hours")
    except Exception as e:
        print(f"Error getting annual leave balance: {e}")

    # 2. Get future scheduled leave
    try:
        scheduled_annual_leave = get_future_scheduled_leave(employee_id, "Annual")
        print(f"Scheduled Annual Leave: {scheduled_annual_leave} hours")
    except Exception as e:
        print(f"Error getting scheduled leave: {e}")

    # Get and display comprehensive leave summary
    try:
        summary = get_leave_summary(employee_id)
        
        print(f"\n=== Leave Summary for {summary['employee_name']} ===\n")
        
        print("Current Leave Balances:")
        print("-" * 40)
        for leave_type, balance in summary['current_balances'].items():
            print(f"{leave_type}: {balance:.2f} hours ({balance/8:.1f} days)")
        
        print("\nFuture Leave Requests:")
        print("-" * 40)
        #if summary['future_leave_requests']:
            # do nothing
            #for request in summary['future_leave_requests']:
                #print(f"Date: {request['date']}")
                #print(f"Type: {request['leave_type']}")
                #print(f"Amount: {request['days']:.1f} days")
                #print(f"Status: {request['status']}")
                #print("-" * 20)
        #else:
        #    print("No future leave requests found")
            
        print("\nPredicted Balances (6 months):")
        print("-" * 40)
        for leave_type, balances in summary['future_balances'].items():
            print(f"\n{leave_type}:")
            print(f"  Current Balance:   {balances['raw_balance']:.2f} hours ({balances['raw_balance']/8:.1f} days)")
            print(f"  Accrued Balance:   {balances['accrued']:.2f} hours ({balances['accrued']/8:.1f} days)")
            print(f"  Future Requests:   {balances['requested']:.2f} hours ({balances['requested']/8:.1f} days)")
            print(f"  Future Remaining:  {balances['remaining']:.2f} hours ({balances['remaining']/8:.1f} days)")
    except Exception as e:
        print(f"Error getting leave summary: {e}")

    # 4. Predict future leave balance
    try:
        future_date = date.today() + timedelta(days=90)
        predicted_balance = predict_leave_balance(employee_id, "Annual", future_date)
        print(f"\nPredicted Annual Leave Balance on {future_date}: {predicted_balance:.2f} hours")
    except Exception as e:
        print(f"Error predicting leave balance: {e}")

    # 5. Create a leave request
    try:
        print("\nCreating a new leave request...")
        print("\nExiting as we're not ready to create a leave request right now...")
        sys.exit(0)
        start_date = (date.today() + timedelta(days=30)).isoformat()
        end_date = (date.today() + timedelta(days=35)).isoformat()
        
        # Note: The number of hours should match the employee's work schedule for the period.
        request = create_leave_request(
            employee_id,
            "Annual",
            start_date,
            end_date,
            "Vacation",
            40.0 # Example: 5 days * 8 hours/day
        )
        leave_application_id = request.get("leaveApplications", [{}])[0].get("leaveApplicationID")
        print(f"Leave request created with ID: {leave_application_id}")

        # The following approve/reject functions are conceptual and may need real-world testing and adjustment.
        # print(f"Approving leave request {leave_application_id}...")
        # approve_leave_request(leave_application_id)
        # print("Leave request approved.")

        # print(f"Rejecting leave request {leave_application_id}...")
        # reject_leave_request(leave_application_id)
        # print("Leave request rejected.")

    except Exception as e:
        print(f"Error creating leave request: {e}")


def update_Wrike_bot(Bot_Task_ID, newStatus, New_Description):
    # Set Melbourne timezone
    mel_tz = pytz.timezone("Australia/Melbourne")

    # Get current date in Melbourne timezone
    melbourne_now = datetime.now(mel_tz)

    # Format the date
    date_str = melbourne_now.strftime("%d-%m-%Y %H:%M:%S")  # e.g., "2025-06-26"



    logging.info("Updating Job History")
    job_history=f'{New_Description}\n\n{JOB_HISTORY_GLOBAL}'
    job_history = job_history[:1000]
    New_Description=New_Description[:1000]
    # Append to your string
    custom_fields = [{
        "id": "IEAF5D2JJUAIEGRD",
        "value": wrike_text_cf_value(New_Description),
        "id": "IEAF5D2JJUAIWT6G",
        "value": wrike_text_cf_value(job_history),
    }]

    params = {
        "customFields": json.dumps(custom_fields, ensure_ascii=False),
        "customStatus": newStatus,
    }

    response = WRIKE_request("PUT", f"/tasks/{Bot_Task_ID}", params=params)
    logging.info("Updating Wrike Bot Task ID %s to status %s", Bot_Task_ID, newStatus)

    #last job status field
    #WRIKE_URL = f'https://www.wrike.com/api/v4/tasks/{Bot_Task_ID}?customFields=[{{"id":"IEAF5D2JJUAIEGRD","value":"{New_Description}"}}]&customStatus={newStatus}'
    #response = requests.put(WRIKE_URL, headers=wrike_headers)
    #response = WRIKE_request("PUT", WRIKE_URL)

    #logging.debug(f"Response to {WRIKE_URL} is {response}")
    #job history field
    #WRIKE_URL = f'https://www.wrike.com/api/v4/tasks/{Bot_Task_ID}?customFields=[{{"id":"IEAF5D2JJUAIWT6G","value":"{job_history}"}}]&customStatus={newStatus}'
    #response = requests.put(WRIKE_URL, headers=wrike_headers)
    #response = WRIKE_request("PUT", WRIKE_URL)
    #logging.debug(f"Response to {WRIKE_URL} is {response}")

    if response.status_code != 200:
        logging.error(f"Error Updating Bot task id {Bot_Task_ID} to status {newStatus}")
        logging.error(f"Response: {response}")
        sys.exit(1)


if __name__ == "__main__":


    logger.info("="*60)
    logger.info("Xero Payroll webhook handler started")
    logger.info(f"Number of arguments: {len(sys.argv)}")
    if len(sys.argv) > 1:
        logger.info(f"First argument (payload): {sys.argv[1][:100]}...")
    logger.info("="*60)
    

    # Check if we have a webhook payload
    if len(sys.argv) > 1:
        try:
            # Parse the webhook payload from command line argument
            logger.info("Received webhook payload, parsing JSON...")
            payload = json.loads(sys.argv[1])
            
            logger.info(f"Payload decoded successfully: {payload}")
            
            if isinstance(payload, list) and payload:
                bot_task_id = payload[0].get("taskId", "unknown_task_id")
            elif isinstance(payload, dict):
                bot_task_id = payload.get("taskId", "unknown_task_id")
            else:
                bot_task_id = "unknown_task_id"

            logger.info("taskId: %s", bot_task_id)


            
            skip_duplicate_check = False

            # Process the webhook payload
            result = handle_webhook_payload(payload)
            
            # Print the result as JSON
            json_output = json.dumps(result, indent=2)
            print(json_output)
            logger.info(f"Response sent: {json_output}")

            

            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding webhook payload: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": f"Invalid JSON payload: {str(e)}"
            }
            print(json.dumps(error_response, indent=2))
            bot_response=update_Wrike_bot(bot_task_id, status_error, json.dumps(error_response, indent=2))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": str(e)
            }
            print(json.dumps(error_response, indent=2))
            bot_response=update_Wrike_bot(bot_task_id, status_error, json.dumps(error_response, indent=2))
            sys.exit(1)
    else:
        logger.info("No webhook payload provided, running in interactive mode")
        
        # No webhook payload, run in interactive mode
        main()
