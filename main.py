# main.py

import sys
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


if __name__ == "__main__":
    main()
