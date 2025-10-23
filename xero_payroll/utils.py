# utils.py

from datetime import date, timedelta

# As per Fair Work Australia, full-time and part-time employees get 4 weeks of annual leave.
# This is accrued based on the number of hours they work.
# For a standard 38-hour week, this is 2.923 hours of leave per week.
# (4 weeks * 38 hours) / 52 weeks = 2.923 hours/week
HOURS_PER_WEEK = 38
WEEKS_PER_YEAR = 52
ANNUAL_LEAVE_WEEKS = 4
ANNUAL_LEAVE_ACCRUAL_RATE_PER_HOUR = (ANNUAL_LEAVE_WEEKS * HOURS_PER_WEEK) / (WEEKS_PER_YEAR * HOURS_PER_WEEK)

def calculate_accrued_leave(start_date: date, end_date: date, hours_worked_per_week: float) -> float:
    """
    Calculates the amount of annual leave accrued between two dates.
    This is a simplified model and might need adjustment based on specific pay calendars
    and employment contracts.
    """
    if start_date > end_date:
        return 0.0

    days_worked = (end_date - start_date).days
    weeks_worked = days_worked / 7
    total_hours_worked = weeks_worked * hours_worked_per_week
    accrued_hours = total_hours_worked * ANNUAL_LEAVE_ACCRUAL_RATE_PER_HOUR
    return accrued_hours
