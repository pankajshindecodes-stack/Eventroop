# eventroop_backend/celery.py
import os
from celery import Celery
from celery.schedules import crontab,schedule,timedelta
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventroop_backend.settings')

app = Celery('eventroop_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Configure Celery Beat Schedule
app.conf.beat_schedule = {
     'daily-digest': {
        'task': 'notifications.tasks.send_daily_digest',
        'schedule': crontab(hour=8, minute=0),  # Every day at 8am
    },
    'mark-attendance-present': {
        'task': 'attendance.tasks.mark_attendance_present',
        # 'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
        # 'schedule': schedule(timedelta(days=1)),  # Run daily
        'schedule': crontab(hour='0-23', minute='*/1'),  # Run every 1 minutes


    },
}

app.conf.timezone = settings.TIME_ZONE