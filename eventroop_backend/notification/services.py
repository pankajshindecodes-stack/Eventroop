# notifications/services.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.mail import send_mail
from .models import Notification
from .tasks import send_email_task, send_push_task

channel_layer = get_channel_layer()

def notify(recipient, title, message, notif_type='system', sender=None, data=None, send_email=False, send_push=False):
    """
    Central function to create and dispatch all notification types.
    Usage: notify(user, "New Like", "Alice liked your post", notif_type='like', send_email=True)
    """
    notif = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notif_type=notif_type,
        title=title,
        message=message,
        data=data or {},
    )

    # 1. Real-time via WebSocket
    _push_to_websocket(notif)

    # 2. Email (async via Celery)
    if send_email and recipient.email:
        send_email_task.delay(recipient.email, title, message)

    # 3. Push notification (async via Celery)
    if send_push:
        send_push_task.delay(recipient.id, title, message)

    return notif


def _push_to_websocket(notif):
    group_name = f'notifications_{notif.recipient.id}'
    async_to_sync(channel_layer.group_send)(group_name, {
        'type': 'send_notification',
        'data': {
            'type':       'new_notification',
            'id':         notif.id,
            'notif_type': notif.notif_type,
            'title':      notif.title,
            'message':    notif.message,
            'data':       notif.data,
            'created_at': notif.created_at.isoformat(),
        }
    })