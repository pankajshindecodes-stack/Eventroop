from django.db import models
from accounts.models import CustomUser

class Notification(models.Model):
    TYPES = [
        ('operational','operational'),
        ('system','System'),
        ('alert','Alert'),
        ('task','Task'),
    ]

    recipient  = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    sender     = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    notif_type = models.CharField(max_length=20, choices=TYPES, default='system')
    title      = models.CharField(max_length=255)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    data       = models.JSONField(default=dict, blank=True)   # extra payload for frontend
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] → {self.recipient} | {self.title}"