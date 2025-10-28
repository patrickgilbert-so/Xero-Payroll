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
    today = date.today().isoformat()
    
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
    
    total_hours = 0.0
    for app in applications:
        if (app.get("EmployeeID") == employee_id and 
            app.get("LeaveTypeID") == leave_type_id and 
            app.get("StartDate") > today and
            app.get("Status") == "APPROVED"):
            
            leave_periods = app.get("LeavePeriods", [])
            for period in leave_periods:
                total_hours += float(period.get("NumberOfUnits", 0.0))
                print(f"Found approved leave: {app.get('StartDate')} - {app.get('EndDate')}, "
                      f"Hours: {period.get('NumberOfUnits')}")
                
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
    # The Xero API might not allow direct PUT/POST to update a leave balance.
    # This is a conceptual function. You would typically adjust balances
    # through pay items in a pay run.
    print("Warning: Direct leave balance updates may not be supported. "
          "This is a conceptual function.")
    
    # Example of what the payload *could* look like if it were supported.
    data = {
        "employeeID": employee_id,
        "leaveBalances": [
            {
                "leaveTypeID": LEAVE_TYPE_IDS[leave_type],
                "leaveBalance": new_balance
            }
        ]
    }
    # This endpoint is hypothetical.
    # return xero_api_client.post(f"employees/{employee_id}", data)
    raise NotImplementedError("Direct leave balance updates are not typically supported via the API.")
