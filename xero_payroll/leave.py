# leave.py

from datetime import date, datetime
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
        return 0.0
    
    # Search by leave name
    for balance in employee.get("LeaveBalances", []):
        if balance.get("LeaveName") == xero_leave_name:
            return float(balance.get("NumberOfUnits", 0.0))
    
    return 0.0

def get_future_scheduled_leave(employee_id: str, leave_type: str) -> float:
    """Finds the future scheduled leave for an employee for a given leave category."""
    from datetime import datetime
    today = date.today()
    
    # Get all leave applications
    response = xero_api_client.get("LeaveApplications")
    applications = response.get("LeaveApplications", [])
    
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
    #print(f"\nEmployee ID: {employee_id}")
    #print(f"Leave Type ID: {leave_type_id}")
    
    total_hours = 0.0
    future_applications = []
    for app in applications:
        # Clean up the IDs by stripping whitespace and ensuring they're strings
        app_employee_id = str(app.get("EmployeeID", "")).strip()
        app_leave_type_id = str(app.get("LeaveTypeID", "")).strip()
        employee_id = str(employee_id).strip()
        leave_type_id = str(leave_type_id).strip()
        
        # Debug output for each application
        #print(f"\nChecking application:")
        #print(f"Application Employee ID: '{app_employee_id}' (len: {len(app_employee_id)})")
        #print(f"Expected Employee ID:    '{employee_id}' (len: {len(employee_id)})")
        #print(f"Application Leave Type:  '{app_leave_type_id}' (len: {len(app_leave_type_id)})")
        #print(f"Expected Leave Type:     '{leave_type_id}' (len: {len(leave_type_id)})")
        
        # Check byte-by-byte comparison
        #print("Employee ID bytes:", [ord(c) for c in app_employee_id])
        #print("Expected ID bytes:", [ord(c) for c in employee_id])
        
        # Check if this application belongs to our employee
        if app_employee_id != employee_id:
            #print("-> Employee ID did not match")
            continue
            
        # Check if this is the right leave type
        if app_leave_type_id != leave_type_id:
            #print("-> Leave Type ID did not match")
            continue
            
        # Process leave application dates
        start_date_str = app.get("StartDate", "")
        if start_date_str:
            try:
                # Extract timestamp from Xero date format
                timestamp = int(start_date_str.split('(')[1].split(')')[0].split('+')[0]) / 1000
                app_date = datetime.fromtimestamp(timestamp).date()
                
                #print(f"\nProcessing Leave Application:")
                #print(f"Title: {app.get('Title', 'Untitled')}")
                #print(f"Start Date: {app_date}")
                #print(f"Today: {today}")
                
                if app_date <= today:
                    #print(f"-> Skipping as {app_date} is not in the future")
                    continue
                
                # Found a future leave application, check its status
                periods = app.get('LeavePeriods', [])
                if not periods:
                    #print("-> No leave periods found")
                    continue
                    
                # Check if any periods are approved or processed
                valid_statuses = {'APPROVED', 'PROCESSED'}
                valid_periods = [p for p in periods if p.get('LeavePeriodStatus') in valid_statuses]
                
                if not valid_periods:
                    print("-> No approved or processed leave periods found")
                    continue
                
                print(f"-> Found {len(valid_periods)} approved/processed leave periods!")
                for period in valid_periods:
                    #print(f"   - Hours: {period.get('NumberOfUnits')}")
                    #print(f"     Status: {period.get('LeavePeriodStatus')}")
                    #print(f"     Period: {period.get('PayPeriodStartDate')} to {period.get('PayPeriodEndDate')}")
                    total_hours += float(period.get('NumberOfUnits', 0.0))
                
            except Exception as e:
                print(f"Warning: Could not process leave application: {str(e)}")
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
        #for app in future_applications:
        #    print(f"- {app['title']}: {app['start']} to {app['end']}, Hours: {app['hours']}")
    else:
        print("\nNo future leave applications found for this employee and leave type")
                
    return total_hours

def get_leave_summary(employee_id: str) -> dict:
    """Returns a comprehensive leave summary for all categories for the selected employee."""
    from datetime import datetime, timedelta
    
    # Get employee details and current balances
    response = xero_api_client.get(f"Employees/{employee_id}")
    employee = response.get("Employees", [{}])[0]
    employee_name = f"{employee.get('FirstName', '')} {employee.get('LastName', '')}".strip()
    
    # Initialize summary structure
    summary = {
        "employee_name": employee_name,
        "current_balances": {},
        "future_leave_requests": [],
        "future_balances": {}
    }
    
    # Process current balances and get leave type mappings
    leave_type_mapping = {}  # Maps LeaveTypeID to LeaveName
    for balance in employee.get("LeaveBalances", []):
        leave_name = balance.get("LeaveName")
        if not leave_name:
            continue
            
        leave_type_id = balance.get("LeaveTypeID")
        current_balance = float(balance.get("NumberOfUnits", 0.0))
        
        summary["current_balances"][leave_name] = current_balance
        leave_type_mapping[leave_type_id] = leave_name
        
        # Initialize future balances
        summary["future_balances"][leave_name] = {
            "raw_balance": current_balance,  # Will be updated with accrual
            "requested": 0.0,
            "remaining": current_balance  # Will be updated after calculating requests
        }
    
    # Get future leave requests
    today = datetime.now().date()
    six_months = today + timedelta(days=180)
    
    response = xero_api_client.get("LeaveApplications")
    for app in response.get("LeaveApplications", []):
        if app.get("EmployeeID") != employee_id:
            continue
            
        # Parse leave application date
        start_date_str = app.get("StartDate", "")
        if not start_date_str:
            continue
            
        try:
            timestamp = int(start_date_str.split('(')[1].split(')')[0].split('+')[0]) / 1000
            start_date = datetime.fromtimestamp(timestamp).date()
            
            # Skip if not in the future
            if start_date <= today:
                continue
                
            # Get the leave details
            leave_type = leave_type_mapping.get(app.get("LeaveTypeID"))
            if not leave_type:
                continue
                
            # Calculate total hours for this request
            total_hours = sum(
                float(period.get("NumberOfUnits", 0.0))
                for period in app.get("LeavePeriods", [])
                if period.get("LeavePeriodStatus") in {"APPROVED", "PROCESSED"}
            )
            
            if total_hours > 0:
                # Add to future leave requests list
                request_info = {
                    "date": start_date.strftime("%Y-%m-%d"),
                    "leave_type": leave_type,
                    "days": total_hours / 8.0,  # Convert hours to days
                    "status": "Approved/Processed"
                }
                summary["future_leave_requests"].append(request_info)
                
                # Update future balances if within 6 months
                if start_date <= six_months:
                    summary["future_balances"][leave_type]["requested"] += total_hours
                    
        except:
            continue
    
    # Sort future leave requests by date
    summary["future_leave_requests"].sort(key=lambda x: x["date"])
    
    # Calculate future accrual and remaining balances
    for leave_type in summary["future_balances"]:
        # Calculate 6-month future date for accrual prediction
        future_date = six_months
        
        # Get the internal leave type name
        internal_leave_type = None
        for key, value in LEAVE_TYPES.items():
            if value == leave_type:
                internal_leave_type = key
                break
                
        if internal_leave_type:
            # Convert to our internal leave type
            current = summary["future_balances"][leave_type]["raw_balance"]
            
            # Get the predicted balance which includes accrual
            predicted = predict_leave_balance(employee_id, internal_leave_type, future_date)
            
            # Calculate only the accrued portion (always positive)
            accrued_amount = abs(predicted - current)
            
            # Don't accrue for Other Unpaid Leave
            if leave_type == "Other Unpaid Leave":
                accrued_amount = 0.0
        else:
            accrued_amount = 0.0
            
        summary["future_balances"][leave_type]["accrued"] = accrued_amount
        summary["future_balances"][leave_type]["remaining"] = (
            summary["future_balances"][leave_type]["raw_balance"] +
            accrued_amount -
            summary["future_balances"][leave_type]["requested"]
        )
    
    return summary

def predict_leave_balance(employee_id: str, leave_type: str, future_date: date, hours_per_week: float = 38.0) -> float:
    """
    Predicts the leave balance for an employee on a future date.
    Calculates accrual for different leave types based on standard rates.
    """
    # Get current balance
    current_balance = get_employee_leave_balance(employee_id, leave_type)
    
    # Get scheduled leave
    total_scheduled = 0.0
    
    # Convert internal leave type to Xero leave type name for balance check
    xero_leave_name = LEAVE_TYPES.get(leave_type)
    if not xero_leave_name:
        return current_balance  # Return current balance if leave type not found
    
    # Calculate accrual based on leave type
    today = date.today()
    accrued_leave = 0.0
    
    # Calculate accrual rates based on leave type name from Xero
    days_between = (future_date - today).days
    daily_hours = hours_per_week / 5  # Convert weekly hours to daily hours
    
    if xero_leave_name == "Annual Leave":
        # Standard annual leave accrual (4 weeks per year)
        accrued_leave = calculate_accrued_leave(today, future_date, hours_per_week)
    elif xero_leave_name == "Personal/Carer's Leave":
        # Personal/Carer's leave accrues at 10 days per year
        yearly_hours = 10 * daily_hours  # 10 days per year
        accrued_leave = (yearly_hours / 365) * days_between
    elif xero_leave_name == "Long Service Leave":
        # Long Service Leave accrues at 6.5 weeks per 10 years
        # 6.5 weeks = 32.5 days per 10 years = 3.25 days per year
        yearly_days = 3.25  # days per year
        yearly_hours = yearly_days * daily_hours
        accrued_leave = abs((yearly_hours / 365) * days_between)  # Ensure positive accrual
    # Other leave types don't accrue
    else:
        accrued_leave = 0.0
    
    # Get scheduled leave
    response = xero_api_client.get("LeaveApplications")
    applications = response.get("LeaveApplications", [])
    
    # Calculate scheduled leave
    response = xero_api_client.get("LeaveApplications")
    applications = response.get("LeaveApplications", [])
    
    for app in applications:
        if app.get("EmployeeID") != employee_id:
            continue
            
        start_date_str = app.get("StartDate", "")
        if not start_date_str:
            continue
            
        try:
            timestamp = int(start_date_str.split('(')[1].split(')')[0].split('+')[0]) / 1000
            start_date = datetime.fromtimestamp(timestamp).date()
            
            if start_date <= future_date:
                # Sum up approved/processed leave periods
                leave_periods = app.get("LeavePeriods", [])
                total_scheduled += sum(
                    float(period.get("NumberOfUnits", 0.0))
                    for period in leave_periods
                    if period.get("LeavePeriodStatus") in {"APPROVED", "PROCESSED"}
                )
        except:
            continue
    
    return current_balance + accrued_leave - total_scheduled

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
