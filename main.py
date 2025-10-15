# g:\Users\gilbe\PycharmProjects\Xero Payroll\main.py

from datetime import date, timedelta
from xero_payroll.api import xero_api_client
from xero_payroll.leave import (
    get_employee_leave_balance,
    get_future_scheduled_leave,
    get_leave_summary,
    predict_leave_balance,
    create_leave_request,
    approve_leave_request,
    reject_leave_request,
    LEAVE_TYPE_IDS,
)

def main():
    """
    Main function to demonstrate the Xero Payroll API integration.
    
    This function requires you to have a valid token.
    You'll need to run an OAuth 2.0 flow to get one.
    """
    # --- Authentication ---
    # This is a placeholder for the authentication process.
    # In a real application, you would redirect the user to the authorization URL,
    # get the callback, and then fetch the token.
    if not xero_api_client.token:
        print(">>> Step 1: Get Authorization URL")
        auth_url, _ = xero_api_client.get_authorization_url()
        print("Please go to this URL and authorize the application:", auth_url)
        
        # In a web app, you would handle the redirect. Here, we'll fake it.
        redirect_response = input("Paste the full redirect URL here: ")
        
        print("\n>>> Step 2: Fetching Token")
        try:
            xero_api_client.fetch_token(redirect_response)
            print("Token fetched successfully!")
        except Exception as e:
            print(f"Error fetching token: {e}")
            return

    # --- Example Usage ---
    # Replace with a real EmployeeID from your Xero account.
    employee_id = "your_employee_id_here" 
    
    if employee_id == "your_employee_id_here":
        print("\nPlease update 'employee_id' in main.py with a real EmployeeID.")
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

    # 3. Get leave summary
    try:
        summary = get_leave_summary(employee_id)
        print("\nLeave Summary:")
        for leave_type, data in summary.items():
            print(f"  {leave_type}:")
            print(f"    Current Balance: {data['current_balance']} hours")
            print(f"    Scheduled Leave: {data['scheduled_leave']} hours")
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
