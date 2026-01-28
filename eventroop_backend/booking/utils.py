# booking/utils.py
from decimal import Decimal, ROUND_HALF_UP
from .models import PeriodChoices
from django.utils.dateparse import parse_datetime

def calculate_package_cost(package, start_dt, end_dt):
    if not start_dt or not end_dt or end_dt <= start_dt:
        return Decimal("0.00")
    
    start_dt = parse_datetime(str(start_dt))
    end_dt = parse_datetime(str(end_dt))

    duration = end_dt - start_dt

    def months_between(start, end):
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day > start.day:
            months += 1
        return max(1, months)

    if package.period == PeriodChoices.HOURLY:
        hours = Decimal(duration.total_seconds()) / Decimal("3600")
        total = hours * package.price

    elif package.period == PeriodChoices.DAILY:
        days = Decimal(max(1, duration.days + (1 if duration.seconds else 0)))
        total = days * package.price

    elif package.period == PeriodChoices.MONTHLY:
        months = Decimal(months_between(start_dt, end_dt))
        total = months * package.price

    else:
        return Decimal("0.00")

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
