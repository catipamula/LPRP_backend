from django.core.mail import send_mail
from django.conf import settings
from .models import Notification
import logging

logger = logging.getLogger(__name__)

def create_and_send_notification(user, complaint, title, message, notification_type='STATUS_CHANGE'):
    """
    Creates an in-app database notification and attempts to send an email notification if user has an email.
    Safely catches any email transport errors.
    """
    if not user:
        return None

    # In-app notification
    notification = Notification.objects.create(
        user=user,
        complaint=complaint,
        title=title,
        message=message,
        notification_type=notification_type
    )

    # Email notification
    user_email = user.email or (complaint.citizen_email if complaint else None)
    if user_email:
        try:
            subject = f"[Smart City Portal] {title}"
            body = f"""Dear {user.get_full_name() or user.username},

{message}

Complaint Tracking ID: {complaint.tracking_id if complaint else 'N/A'}
Status: {complaint.get_status_display() if complaint else 'N/A'}

You can track or view updates on the Smart City Portal at any time.

Regards,
Smart City Problem Resolution Administration
"""
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@smartcity.gov.in'),
                recipient_list=[user_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send email notification to {user_email}: {e}")

    return notification
