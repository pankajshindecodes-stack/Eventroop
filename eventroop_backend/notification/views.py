from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer, NotificationUpdateSerializer


class NotificationListView(generics.ListAPIView):
    """
    GET /api/notifications/
    Query params:
      ?unread=true   → only unread
      ?type=like     → filter by type
      ?page=1        → pagination (default page size 20)
    """
    serializer_class   = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related('sender')

        unread = self.request.query_params.get('unread')
        if unread and unread.lower() == 'true':
            qs = qs.filter(is_read=False)

        notif_type = self.request.query_params.get('type')
        if notif_type:
            qs = qs.filter(notif_type=notif_type)

        return qs

    def list(self, request, *args, **kwargs):
        queryset     = self.get_queryset()
        unread_count = queryset.filter(is_read=False).count() if not request.query_params.get('unread') else queryset.count()
        page         = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response   = self.get_paginated_response(serializer.data)
            response.data['unread_count'] = Notification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results':      serializer.data,
            'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """GET /api/notifications/unread-count/"""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'unread_count': count})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_read(request, pk):
    """PATCH /api/notifications/<pk>/read/"""
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return Response(NotificationSerializer(notif).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """
    PATCH /api/notifications/mark-all-read/
    Body (optional): { "ids": [1, 2, 3] }  → marks specific ones
    No body → marks ALL unread
    """
    serializer = NotificationUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ids = serializer.validated_data.get('ids')

    qs = Notification.objects.filter(recipient=request.user, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)

    updated = qs.update(is_read=True)
    return Response({'marked_read': updated})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    """DELETE /api/notifications/<pk>/"""
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all(request):
    """DELETE /api/notifications/clear/"""
    deleted, _ = Notification.objects.filter(recipient=request.user).delete()
    return Response({'deleted': deleted})


# ─── Internal helper used by signals / services ──────────────────────────────

def create_notification(recipient, title, message, notif_type='system',
                        sender=None, data=None, send_email=False, send_push=False):
    """
    Call this from signals, views, or Celery tasks to create + dispatch a notification.

    Example:
        from notifications.views import create_notification
        create_notification(
            recipient  = user,
            title      = "New Like ❤️",
            message    = "Alice liked your post.",
            notif_type = 'like',
            sender     = alice,
            send_email = True,
        )
    """
    notif = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notif_type=notif_type,
        title=title,
        message=message,
        data=data or {},
    )

    # Real-time WebSocket push
    _ws_push(notif)

    # Async email
    if send_email and recipient.email:
        from .tasks import send_email_task
        send_email_task.delay(recipient.email, title, message)

    # Async push notification
    if send_push:
        from .tasks import send_push_task
        send_push_task.delay(recipient.id, title, message)

    return notif


def _ws_push(notif):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{notif.recipient.id}',
            {
                'type': 'send_notification',
                'data': NotificationSerializer(notif).data,
            }
        )
    except Exception:
        pass  # Channels not configured — silently skip