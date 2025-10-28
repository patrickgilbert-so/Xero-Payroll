# leave.py

from datetime import date
from .api import xero_api_client
from .utils import calculate_accrued_leave

# --- Leave Types ---
# These are the standard leave types mapped to their display names in Xero
LEAVE_TYPES = {
    "Annual": "Annual Leave",
    "LongService": "Long Service Leave",
    "PersonalCarers": "Personal/Carer's Leave",
    # Add other leave types as they become available in your Xero setup
}

def get_employee_leave_balance(employee_id: str, leave_type: str) -> float:
    """Retrieves the current leave balance for a selected employee and leave type."""
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    
    # Get the Xero leave name for our internal leave type
    xero_leave_name = LEAVE_TYPES.get(leave_type)
    if not xero_leave_name:
        print(f"Warning: Leave type '{leave_type}' is not configured in this Xero account")
        return 0.0
    
    # Debug output
    print(f"\nSearching for leave type: {xero_leave_name}")
    print("Available leave balances:")
    for balance in employee.get("LeaveBalances", []):
        print(f"Leave Type: {balance.get('LeaveName')}, Balance: {balance.get('NumberOfUnits')}")
    
    # Search by leave name
    for balance in employee.get("LeaveBalances", []):
        if balance.get("LeaveName") == xero_leave_name:
            return float(balance.get("NumberOfUnits", 0.0))
    
    return 0.0

def get_future_scheduled_leave(employee_id: str, leave_type: str) -> float:
    """Finds the future scheduled leave for an employee for a given leave category."""
    today = date.today()
    print(f"\nSearching for leave after {today}")
    
    # Get the Xero leave name for our internal leave type
    xero_leave_name = LEAVE_TYPES.get(leave_type)
    if not xero_leave_name:
        print(f"Warning: Leave type '{leave_type}' is not configured in this Xero account")
        return 0.0
    
    # First get the leave type ID from the employee's leave balances
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    
    leave_type_id = None
    for balance in employee.get("LeaveBalances", []):
        if balance.get("LeaveName") == xero_leave_name:
            leave_type_id = balance.get("LeaveTypeID")
            break
    
    if not leave_type_id:
        print(f"Warning: Could not find leave type ID for {xero_leave_name}")
        return 0.0

    response = xero_api_client.get("LeaveApplications")
    applications = response.get("LeaveApplications", [])
    
    # Debug output
    print(f"\nSearching for future leave applications of type: {leave_type}")
    print(f"Found {len(applications)} total leave applications")
    
    # Debug output to understand what we're working with
    print(f"\nEmployee ID: {employee_id}")
    print(f"Leave Type ID: {leave_type_id}")
    
    total_hours = 0.0
    future_applications = []
    for app in applications:
        # Clean up the IDs by stripping whitespace and ensuring they're strings
        app_employee_id = str(app.get("EmployeeID", "")).strip()
        app_leave_type_id = str(app.get("LeaveTypeID", "")).strip()
        employee_id = str(employee_id).strip()
        leave_type_id = str(leave_type_id).strip()
        
        # Debug output for each application
        print(f"\nChecking application:")
        print(f"Application Employee ID: '{app_employee_id}' (len: {len(app_employee_id)})")
        print(f"Expected Employee ID:    '{employee_id}' (len: {len(employee_id)})")
        print(f"Application Leave Type:  '{app_leave_type_id}' (len: {len(app_leave_type_id)})")
        print(f"Expected Leave Type:     '{leave_type_id}' (len: {len(leave_type_id)})")
        
        # Check byte-by-byte comparison
        print("Employee ID bytes:", [ord(c) for c in app_employee_id])
        print("Expected ID bytes:", [ord(c) for c in employee_id])
        
        # Check if this application belongs to our employee
        if app_employee_id != employee_id:
            print("-> Employee ID did not match")
            continue
            
        # Check if this is the right leave type
        if app_leave_type_id != leave_type_id:
            print("-> Leave Type ID did not match")
            continue
            
        # Convert Unix timestamp to date
        # Xero dates are in format "/Date(1234567890000+0000)/"
        start_date_str = app.get("StartDate", "")
        if start_date_str:
            try:
                timestamp = int(start_date_str.split('(')[1].split(')')[0].split('+')[0]) / 1000
                from datetime import datetime
                app_date = datetime.fromtimestamp(timestamp).date()
                today_date = datetime.strptime(today, "%Y-%m-%d").date()
                
                print(f"Start Date: {app_date}, Today: {today_date}")
                if app_date <= today_date:
                    print(f"-> Skipping as {app_date} is not in the future")
                    continue
                
                print(f"-> Found future leave application!")
                
            except Exception as e:
                print(f"Warning: Could not parse date {start_date_str}: {str(e)}")
                continue
        
        # Only include APPROVED or SUBMITTED applications
        period_status = next((p.get("LeavePeriodStatus") for p in app.get("LeavePeriods", [])), None)
        if period_status not in ["PROCESSED", "APPROVED"]:
            continue
            
        # Add up the hours
        leave_periods = app.get("LeavePeriods", [])
        period_hours = sum(float(period.get("NumberOfUnits", 0.0)) for period in leave_periods)
        total_hours += period_hours
        
        # Store for debug output
        future_applications.append({
            'title': app.get('Title', 'Untitled'),
            'start': app.get('StartDate'),
            'end': app.get('EndDate'),
            'hours': period_hours
        })
    
    # Debug output
    if future_applications:
        print(f"\nFound {len(future_applications)} future leave application(s):")
        for app in future_applications:
            print(f"- {app['title']}: {app['start']} to {app['end']}, Hours: {app['hours']}")
    else:
        print("\nNo future leave applications found for this employee and leave type")
                
    return total_hours

def get_leave_summary(employee_id: str) -> dict:
    """Returns a leave summary for all categories for the selected employee."""
    # First get all available leave types from the employee record
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    
    summary = {}
    for balance in employee.get("LeaveBalances", []):
        leave_name = balance.get("LeaveName")
        if not leave_name:
            continue
            
        current_balance = float(balance.get("NumberOfUnits", 0.0))
        leave_type_id = balance.get("LeaveTypeID")
        
        # Get scheduled leave for this leave type
        scheduled_leave = 0.0
        if leave_type_id:
            response = xero_api_client.get("LeaveApplications", params={
                "where": f'EmployeeID=="{employee_id}" AND LeaveTypeID=="{leave_type_id}" AND StartDate > DateTime.Parse("{date.today().isoformat()}")'
            })
            for app in response.get("LeaveApplications", []):
                if app.get("Status") == "APPROVED":
                    for period in app.get("LeavePeriods", []):
                        scheduled_leave += float(period.get("NumberOfUnits", 0.0))
        
        summary[leave_name] = {
            "current_balance": current_balance,
            "scheduled_leave": scheduled_leave,
        }
    
    return summary

def predict_leave_balance(employee_id: str, leave_type: str, future_date: date, hours_per_week: float = 38.0) -> float:
    """
    Predicts the leave balance for an employee on a future date.
    Note: This is a simplified prediction for Annual Leave only.
    """
    if leave_type != "Annual":
        # For simplicity, this example only calculates accrual for annual leave.
        # Other leave types might not accrue in the same way.
        current_balance = get_employee_leave_balance(employee_id, leave_type)
        scheduled_leave = get_future_scheduled_leave(employee_id, leave_type)
        return current_balance - scheduled_leave

    current_balance = get_employee_leave_balance(employee_id, "Annual")
    scheduled_leave = get_future_scheduled_leave(employee_id, "Annual")
    
    today = date.today()
    accrued_leave = calculate_accrued_leave(today, future_date, hours_per_week)
    
    # This is a simplification. A more accurate model would need to consider
    # leave taken between today and the future date.
    predicted_balance = current_balance + accrued_leave - scheduled_leave
    return predicted_balance

def create_leave_request(employee_id: str, leave_type: str, start_date: str, end_date: str, description: str, hours: float):
    """Lodges a leave request for an employee."""
    # Get the Xero leave name for our internal leave type
    xero_leave_name = LEAVE_TYPES.get(leave_type)
    if not xero_leave_name:
        raise ValueError(f"Leave type '{leave_type}' is not configured in this Xero account")

    # Get the leave type ID from the employee's leave balances
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    
    leave_type_id = None
    for balance in employee.get("LeaveBalances", []):
        if balance.get("LeaveName") == xero_leave_name:
            leave_type_id = balance.get("LeaveTypeID")
            break
            
    if not leave_type_id:
        raise ValueError(f"Could not find leave type ID for {xero_leave_name}")

    data = {
        "EmployeeID": employee_id,
        "LeaveTypeID": leave_type_id,
        "title": description,
        "startDate": start_date,
        "endDate": end_date,
        "leavePeriods": [
            {
                "numberOfUnits": hours,
                "payPeriodEndingDate": end_date, # This might need adjustment
                "leavePeriodStatus": "Scheduled"
            }
        ]
    }
    return xero_api_client.post("leaveapplications", data)

def approve_leave_request(leave_application_id: str):
    """Approves a leave request."""
    # The Xero API uses a POST to a sub-resource for approval.
    # This is a conceptual example. The actual endpoint might differ.
    # It's common to update the status of the leave application.
    # Let's assume we update the status to 'Approved'.
    response = xero_api_client.get(f"leaveapplications/{leave_application_id}")
    leave_application = response['leaveApplications'][0]
    
    # Update the status. This is a simplified example.
    # You might need to adjust the payload based on the API's requirements.
    leave_application['status'] = 'Approved' # This is a guess, check API docs.

    # The endpoint to update is usually the same as the GET but with a PUT/POST
    return xero_api_client.post(f"leaveapplications/{leave_application_id}", leave_application)


def reject_leave_request(leave_application_id: str):
    """Rejects a leave request."""
    # Similar to approval, this would likely involve updating the status.
    response = xero_api_client.get(f"leaveapplications/{leave_application_id}")
    leave_application = response['leaveApplications'][0]
    
    leave_application['status'] = 'Rejected' # This is a guess, check API docs.

    return xero_api_client.post(f"leaveapplications/{leave_application_id}", leave_application)


def update_leave_balance(employee_id: str, leave_type: str, new_balance: float):
    """
    Updates the leave balance for an employee.
    Note: Direct manipulation of leave balances might not be supported or recommended.
    It's often better to create a leave application or a pay run adjustment.
    This function is a placeholder for what might be a more complex operation.
    """
    # Get the Xero leave name for our internal leave type
    xero_leave_name = LEAVE_TYPES.get(leave_type)
    if not xero_leave_name:
        raise ValueError(f"Leave type '{leave_type}' is not configured in this Xero account")

    # Get the leave type ID from the employee's leave balances
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    
    leave_type_id = None
    for balance in employee.get("LeaveBalances", []):
        if balance.get("LeaveName") == xero_leave_name:
            leave_type_id = balance.get("LeaveTypeID")
            break
            
    if not leave_type_id:
        raise ValueError(f"Could not find leave type ID for {xero_leave_name}")
    
    # The Xero API might not allow direct PUT/POST to update a leave balance.
    # This is a conceptual function. You would typically adjust balances
    # through pay items in a pay run.
    print("Warning: Direct leave balance updates may not be supported. "
          "This is a conceptual function.")
    
    # Example of what the payload *could* look like if it were supported.
    data = {
        "EmployeeID": employee_id,
        "LeaveBalances": [
            {
                "LeaveTypeID": leave_type_id,
                "NumberOfUnits": new_balance
            }
        ]
    }
    # This endpoint is hypothetical.
    # return xero_api_client.post(f"Employees/{employee_id}", data)
    raise NotImplementedError("Direct leave balance updates are not typically supported via the API.")
