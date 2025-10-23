# leave.py

from datetime import date
from .api import xero_api_client
from .utils import calculate_accrued_leave

# --- Leave Type IDs ---
# These are examples. You'll need to fetch the actual LeaveTypeIDs from your Xero account
# using the /leavetypes endpoint.
LEAVE_TYPE_IDS = {
    "Annual": "d9419cdd-a489-4569-96a2-6223d4e36d8e",
    "CarersUnpaid": "c8e43958-4c39-43e8-94a3-55594a21b35e",
    "CarersPaid": "f306a00a-7a4a-44d3-b6d1-232a1d5e47c2",
    "CommunityServicePaid": "0f38f5a5-5518-4bf1-a15a-15f08b41b4f8",
    "CommunityServiceUnpaid": "a3d300d3-1e4d-42b6-810c-2005e8f321c9",
    "CompassionatePaid": "e5e6e9b0-ca73-46b0-950d-aa5d35d3e4a9",
    "CompassionateUnpaid": "b31a5f69-64e4-4f33-a44b-3a09f239c2a8",
    "LongService": "a8c6d5f1-dae8-449a-9b6f-1047b41780b3",
    "ParentalUnpaid": "e0c17237-f1eb-47c3-97b3-0032c2a1339a",
    "JuryDuty": "f05199e3-a05a-46f8-9f3b-3509e13211a5",
    "UnauthorisedUnpaid": "a4c27998-720e-45a3-8899-5e83a235c809",
}

def get_employee_leave_balance(employee_id: str, leave_type: str) -> float:
    """Retrieves the current leave balance for a selected employee and leave type."""
    leave_type_id = LEAVE_TYPE_IDS.get(leave_type)
    if not leave_type_id:
        raise ValueError(f"Invalid leave type: {leave_type}")

    response = xero_api_client.get(f"employees/{employee_id}")
    leave_balances = response.get("employees", [{}])[0].get("leaveBalances", [])
    
    for balance in leave_balances:
        if balance.get("leaveTypeID") == leave_type_id:
            return float(balance.get("leaveBalance", 0.0))
    return 0.0

def get_future_scheduled_leave(employee_id: str, leave_type: str) -> float:
    """Finds the future scheduled leave for an employee for a given leave category."""
    leave_type_id = LEAVE_TYPE_IDS.get(leave_type)
    if not leave_type_id:
        raise ValueError(f"Invalid leave type: {leave_type}")

    today = date.today().isoformat()
    params = {
        "where": f'EmployeeID=="{employee_id}" AND LeaveTypeID=="{leave_type_id}" AND StartDate > DateTime.Parse("{today}")'
    }
    response = xero_api_client.get("leaveapplications", params=params)
    
    total_hours = 0.0
    for leave_app in response.get("leaveApplications", []):
        total_hours += float(leave_app.get("leavePeriods", [{}])[0].get("numberOfUnits", 0.0))
        
    return total_hours

def get_leave_summary(employee_id: str) -> dict:
    """Returns a leave summary for all categories for the selected employee."""
    summary = {}
    for leave_type in LEAVE_TYPE_IDS.keys():
        current_balance = get_employee_leave_balance(employee_id, leave_type)
        scheduled_leave = get_future_scheduled_leave(employee_id, leave_type)
        summary[leave_type] = {
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
    leave_type_id = LEAVE_TYPE_IDS.get(leave_type)
    if not leave_type_id:
        raise ValueError(f"Invalid leave type: {leave_type}")

    data = {
        "employeeID": employee_id,
        "leaveTypeID": leave_type_id,
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
