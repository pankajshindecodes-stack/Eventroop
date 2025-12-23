# constants.py

from enum import Enum


class SalaryType(str, Enum):
    """Salary calculation types."""
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    FORTNIGHTLY = "FORTNIGHTLY"
    MONTHLY = "MONTHLY"


class AttendanceStatusCode(str, Enum):
    """Attendance status codes."""
    PRESENT = "P"
    ABSENT = "A"
    HALF_DAY = "HD"
    PAID_LEAVE = "PL"


class SalaryConstants:
    """Constants for salary calculations."""
    HOURS_PER_DAY = 8
    DAYS_PER_WEEK = 6
    DAYS_PER_FORTNIGHT = 12
    DAYS_PER_MONTH = 30