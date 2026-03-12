from rest_framework import serializers
from .models import Notification
from venue_manager.serializers import UserMiniSerializer

class NotificationSerializer(serializers.ModelSerializer):
    sender     = UserMiniSerializer(read_only=True)
    time_ago   = serializers.SerializerMethodField()

    class Meta:
        model  = Notification
        fields = [
            'id', 'notif_type', 'title', 'message',
            'is_read', 'sender', 'data', 'created_at', 'time_ago',
        ]
        read_only_fields = ['id', 'created_at']

    def get_time_ago(self, obj):
        from django.utils import timezone
        from datetime import timedelta

        now   = timezone.now()
        delta = now - obj.created_at

        if delta < timedelta(minutes=1):
            return "just now"
        elif delta < timedelta(hours=1):
            m = int(delta.total_seconds() / 60)
            return f"{m}m ago"
        elif delta < timedelta(days=1):
            h = int(delta.total_seconds() / 3600)
            return f"{h}h ago"
        elif delta < timedelta(days=7):
            d = delta.days
            return f"{d}d ago"
        else:
            return obj.created_at.strftime("%b %d")


class NotificationUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )