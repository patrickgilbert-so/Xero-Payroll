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

def handle_webhook_payload(payload):
    """
    Process webhook payload and return appropriate response.
    
    Args:
        payload (dict or list): The webhook payload containing event data
        
    Returns:
        dict: Response data containing processed information
    """
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

        elif event_type == "Get Leave Summary":
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
            summary = get_leave_summary(employee_id)
            response_data["data"] = summary
            
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
            raise ValueError(f"Unsupported event type: {event_type}")
            
        return response_data
        
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}", exc_info=True)
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

    New_Description = f"{date_str} - Import Completed Successfully "
    if DATE_FROM:
        New_Description = f"{New_Description} from {DATE_FROM} "
    if DATE_TO:
        New_Description = f"{New_Description} to {DATE_TO} "
    if TARGET_PROJECT_NUMBER:
        New_Description=f"{New_Description} for project number {TARGET_PROJECT_NUMBER}"
    New_Description = f"{New_Description}\n - Delete Existing={delete_existing}\n - Skip Duplicates={skip_duplicate_check}"

    logging.info("Updating Job History")
    job_history=f'{New_Description}\n\n{job_history}'
    job_history = job_history[:1000]

    # Append to your string
    #last job status field
    WRIKE_URL = f'https://www.wrike.com/api/v4/tasks/{Bot_Task_ID}?customFields=[{{"id":"IEAF5D2JJUAIEGRD","value":"{New_Description}"}}]&customStatus=IEAF5D2JJMFZTF7H'
    #response = requests.put(WRIKE_URL, headers=wrike_headers)
    response = WRIKE_request("PUT", WRIKE_URL)

    logging.debug(f"Response to {WRIKE_URL} is {response}")
    #job history field
    WRIKE_URL = f'https://www.wrike.com/api/v4/tasks/{Bot_Task_ID}?customFields=[{{"id":"IEAF5D2JJUAIWT6G","value":"{job_history}"}}]&customStatus=IEAF5D2JJMFZTF7H'
    #response = requests.put(WRIKE_URL, headers=wrike_headers)
    response = WRIKE_request("PUT", WRIKE_URL)
    logging.debug(f"Response to {WRIKE_URL} is {response}")

    if response.status_code != 200:
        logging.error(f"Error Updating task id {Bot_Task_ID} with API Call: {WRIKE_URL}")
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
            
            # Process the webhook payload
            result = handle_webhook_payload(payload)
            
            # Print the result as JSON
            json_output = json.dumps(result, indent=2)
            print(json_output)
            logger.info(f"Response sent: {json_output}")

            # update the bot task with status
            # Set Melbourne timezone

            bot_response=update_Wrike_bot(bot_task_id, "Completed", json_output)
            

            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding webhook payload: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": f"Invalid JSON payload: {str(e)}"
            }
            print(json.dumps(error_response, indent=2))
            bot_response=update_Wrike_bot(bot_task_id, "Error", json.dumps(error_response, indent=2))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": str(e)
            }
            print(json.dumps(error_response, indent=2))
            bot_response=update_Wrike_bot(bot_task_id, "Error", json.dumps(error_response, indent=2))
            sys.exit(1)
    else:
        logger.info("No webhook payload provided, running in interactive mode")
        
        # No webhook payload, run in interactive mode
        main()
