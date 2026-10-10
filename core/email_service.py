import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from .models import EmailNotificationLog

logger = logging.getLogger(__name__)

def _get_recipient_email(complaint):
    """
    Get citizen's email address from complaint record or authenticated user profile.
    """
    if complaint.citizen_email and complaint.citizen_email.strip():
        return complaint.citizen_email.strip()
    if complaint.citizen and complaint.citizen.email and complaint.citizen.email.strip():
        return complaint.citizen.email.strip()
    return None

def _send_html_email(recipient, subject, text_content, html_content, complaint, event_type, dedup_key=None):
    """
    Safely sends HTML + Plain text email, logs attempt, and prevents duplicate sends.
    Never raises an exception to the caller.
    """
    if not recipient:
        logger.info(f"No recipient email found for complaint {complaint.tracking_id}. Skipping email.")
        return False

    # Deduplication check
    if dedup_key:
        if EmailNotificationLog.objects.filter(dedup_key=dedup_key, status='SENT').exists():
            logger.info(f"Duplicate email detected with key '{dedup_key}'. Skipping.")
            return False

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@smartcity.gov.in')

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        EmailNotificationLog.objects.create(
            complaint=complaint,
            recipient_email=recipient,
            subject=subject,
            event_type=event_type,
            status='SENT',
            dedup_key=dedup_key,
        )
        logger.info(f"Successfully sent {event_type} email to {recipient} for {complaint.tracking_id}")
        return True

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"Failed to send email to {recipient} for {complaint.tracking_id}: {error_msg}")
        EmailNotificationLog.objects.create(
            complaint=complaint,
            recipient_email=recipient,
            subject=subject,
            event_type=event_type,
            status='FAILED',
            dedup_key=dedup_key,
            error_message=error_msg,
        )
        return False

def _build_email_template(title, header_badge, body_paragraphs, tracking_id, action_url, footer_text=None):
    """
    Constructs a clean, modern responsive HTML template for Smart City notifications.
    """
    frontend_base = getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')
    full_track_url = action_url or f"{frontend_base}/track?id={tracking_id}"

    paragraphs_html = "".join([f'<p style="margin: 0 0 14px 0; line-height: 1.6; color: #334155; font-size: 14px;">{p}</p>' for p in body_paragraphs])

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1); border: 1px solid #e2e8f0;">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 32px 28px; text-align: left;">
        <div style="display: inline-block; padding: 4px 12px; background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 9999px; color: #60a5fa; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
          {header_badge}
        </div>
        <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 700; letter-spacing: -0.5px;">
          Smart City Problem Resolution Portal
        </h1>
        <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px;">
          Civic Complaint Management & Resolution System
        </p>
      </td>
    </tr>

    <!-- Body -->
    <tr>
      <td style="padding: 28px 28px 20px 28px;">
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 18px; margin-bottom: 22px;">
          <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Tracking Reference</div>
          <div style="font-size: 20px; font-weight: 800; color: #1d4ed8; font-family: monospace; margin-top: 2px;">{tracking_id}</div>
        </div>

        {paragraphs_html}

        <!-- CTA Button -->
        <div style="text-align: center; margin: 30px 0 20px 0;">
          <a href="{full_track_url}" target="_blank" style="display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 28px; font-size: 14px; font-weight: 700; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(37,99,235,0.25);">
            Track Complaint Live &rarr;
          </a>
        </div>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 28px; text-align: center; color: #64748b; font-size: 12px; line-height: 1.5;">
        <p style="margin: 0 0 4px 0;">{footer_text or "This is an automated notification from the Municipal Problem Resolution Portal."}</p>
        <p style="margin: 0; color: #94a3b8; font-size: 11px;">Please do not reply directly to this email. For updates, visit your tracking portal.</p>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html

def send_complaint_created_email(complaint):
    """
    Triggered when a new complaint is created.
    """
    recipient = _get_recipient_email(complaint)
    if not recipient:
        return False

    dept_name = complaint.department.name if complaint.department else "Civic Review Queue"
    subject = f"Complaint Registered: [{complaint.tracking_id}] - {complaint.title}"
    dedup_key = f"{complaint.id}_CREATED"

    body_paragraphs = [
        f"Dear <b>{complaint.citizen_name or 'Citizen'}</b>,",
        f"Your civic complaint has been registered successfully on the Smart City Portal.",
        f"<b>Title:</b> {complaint.title}<br>"
        f"<b>Department:</b> {dept_name}<br>"
        f"<b>Priority:</b> {complaint.priority}<br>"
        f"<b>Target SLA:</b> {complaint.sla_due_date.strftime('%d %b %Y, %I:%M %p') if complaint.sla_due_date else 'Standard 48 Hours'}",
        "Our municipal operations team will verify and dispatch this incident to the authorized field officer shortly. You can monitor the progress, chat with officers, and view timeline updates in real-time."
    ]

    text_content = (
        f"Dear {complaint.citizen_name or 'Citizen'},\n\n"
        f"Your civic complaint has been registered successfully.\n"
        f"Tracking ID: {complaint.tracking_id}\n"
        f"Title: {complaint.title}\n"
        f"Department: {dept_name}\n"
        f"Priority: {complaint.priority}\n\n"
        f"Track your complaint online:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')}/track?id={complaint.tracking_id}\n"
    )

    html_content = _build_email_template(
        title=f"Complaint Registered: {complaint.tracking_id}",
        header_badge="Complaint Confirmation",
        body_paragraphs=body_paragraphs,
        tracking_id=complaint.tracking_id,
        action_url=None
    )

    return _send_html_email(recipient, subject, text_content, html_content, complaint, 'COMPLAINT_CREATED', dedup_key)

def send_status_updated_email(complaint, from_status, to_status, notes=None):
    """
    Triggered when complaint status transitions (e.g. IN_PROGRESS, ASSIGNED, UNDER_VERIFICATION).
    """
    recipient = _get_recipient_email(complaint)
    if not recipient:
        return False

    subject = f"Status Update: [{complaint.tracking_id}] changed to {to_status}"
    dedup_key = f"{complaint.id}_STATUS_{from_status}_{to_status}_{timezone.now().strftime('%Y%m%d%H%M')}"

    body_paragraphs = [
        f"Dear <b>{complaint.citizen_name or 'Citizen'}</b>,",
        f"There is a new update on your civic complaint <b>{complaint.title}</b>.",
        f"<b>Previous Status:</b> {from_status}<br>"
        f"<b>New Status:</b> <span style='color: #1d4ed8; font-weight: 700;'>{to_status}</span><br>"
        f"<b>Updated At:</b> {timezone.now().strftime('%d %b %Y, %I:%M %p UTC')}",
    ]

    if notes and notes.strip():
        body_paragraphs.append(f"<b>Officer Remarks:</b><br><div style='padding: 10px 14px; background: #f1f5f9; border-left: 3px solid #3b82f6; border-radius: 4px; font-style: italic;'>\"{notes.strip()}\"</div>")

    text_content = (
        f"Dear {complaint.citizen_name or 'Citizen'},\n\n"
        f"Your complaint status has been updated.\n"
        f"Tracking ID: {complaint.tracking_id}\n"
        f"Previous Status: {from_status}\n"
        f"New Status: {to_status}\n"
        f"Notes: {notes or 'No remarks provided.'}\n\n"
        f"Track your complaint online:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')}/track?id={complaint.tracking_id}\n"
    )

    html_content = _build_email_template(
        title=f"Status Update: {complaint.tracking_id}",
        header_badge="Status Transition",
        body_paragraphs=body_paragraphs,
        tracking_id=complaint.tracking_id,
        action_url=None
    )

    return _send_html_email(recipient, subject, text_content, html_content, complaint, 'STATUS_UPDATED', dedup_key)

def send_complaint_resolved_email(complaint, resolution_notes=None):
    """
    Triggered when complaint is marked as RESOLVED.
    """
    recipient = _get_recipient_email(complaint)
    if not recipient:
        return False

    subject = f"Issue Resolved: [{complaint.tracking_id}] - {complaint.title}"
    dedup_key = f"{complaint.id}_RESOLVED_{timezone.now().strftime('%Y%m%d%H%M')}"

    res_notes = resolution_notes or complaint.resolution_notes or "Field operations completed successfully."

    body_paragraphs = [
        f"Dear <b>{complaint.citizen_name or 'Citizen'}</b>,",
        f"We are pleased to inform you that your complaint <b>{complaint.title}</b> has been marked as <span style='color: #059669; font-weight: 800;'>RESOLVED</span>.",
        f"<b>Department:</b> {complaint.department.name if complaint.department else 'Municipal Operations'}<br>"
        f"<b>Completed On:</b> {timezone.now().strftime('%d %b %Y, %I:%M %p UTC')}",
        f"<b>Resolution Summary:</b><br><div style='padding: 12px 16px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; color: #065f46;'>{res_notes}</div>",
        "Please visit the tracking portal to verify the work done, review uploaded resolution evidence, and submit your satisfaction rating. If you feel the issue was not properly solved, you can also reopen it within 48 hours."
    ]

    text_content = (
        f"Dear {complaint.citizen_name or 'Citizen'},\n\n"
        f"Your complaint has been marked as RESOLVED.\n"
        f"Tracking ID: {complaint.tracking_id}\n"
        f"Title: {complaint.title}\n"
        f"Resolution Summary: {res_notes}\n\n"
        f"Please verify the resolution and provide your feedback at:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')}/track?id={complaint.tracking_id}\n"
    )

    html_content = _build_email_template(
        title=f"Complaint Resolved: {complaint.tracking_id}",
        header_badge="Issue Resolved",
        body_paragraphs=body_paragraphs,
        tracking_id=complaint.tracking_id,
        action_url=None
    )

    return _send_html_email(recipient, subject, text_content, html_content, complaint, 'COMPLAINT_RESOLVED', dedup_key)

def send_complaint_rejected_email(complaint, rejection_reason=None):
    """
    Triggered when complaint is marked as REJECTED.
    """
    recipient = _get_recipient_email(complaint)
    if not recipient:
        return False

    subject = f"Complaint Update: [{complaint.tracking_id}] - Rejected"
    dedup_key = f"{complaint.id}_REJECTED_{timezone.now().strftime('%Y%m%d%H%M')}"
    reason = rejection_reason or complaint.rejection_reason or "Does not meet municipal jurisdiction criteria or duplicate entry."

    body_paragraphs = [
        f"Dear <b>{complaint.citizen_name or 'Citizen'}</b>,",
        f"Your complaint <b>{complaint.title}</b> has been reviewed and marked as <span style='color: #dc2626; font-weight: 800;'>REJECTED</span>.",
        f"<b>Reason for Rejection:</b><br><div style='padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b;'>{reason}</div>",
        "If you believe this was in error, please contact municipal support or submit a new report with additional documentation and correct jurisdiction details."
    ]

    text_content = (
        f"Dear {complaint.citizen_name or 'Citizen'},\n\n"
        f"Your complaint has been marked as REJECTED.\n"
        f"Tracking ID: {complaint.tracking_id}\n"
        f"Reason: {reason}\n\n"
        f"View details at:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')}/track?id={complaint.tracking_id}\n"
    )

    html_content = _build_email_template(
        title=f"Complaint Rejected: {complaint.tracking_id}",
        header_badge="Action Required",
        body_paragraphs=body_paragraphs,
        tracking_id=complaint.tracking_id,
        action_url=None
    )

    return _send_html_email(recipient, subject, text_content, html_content, complaint, 'COMPLAINT_REJECTED', dedup_key)

def send_complaint_reopened_email(complaint, reopen_reason=None):
    """
    Triggered when citizen reopens a resolved complaint.
    """
    recipient = _get_recipient_email(complaint)
    if not recipient:
        return False

    subject = f"Complaint Reopened: [{complaint.tracking_id}]"
    dedup_key = f"{complaint.id}_REOPENED_{timezone.now().strftime('%Y%m%d%H%M')}"
    reason = reopen_reason or complaint.reopen_reason or "Citizen requested further review."

    body_paragraphs = [
        f"Dear <b>{complaint.citizen_name or 'Citizen'}</b>,",
        f"Your request to reopen complaint <b>{complaint.title}</b> has been acknowledged.",
        f"<b>Status:</b> <span style='color: #ea580c; font-weight: 800;'>REOPENED</span>",
        f"<b>Reason Provided:</b><br><div style='padding: 12px 16px; background: #fff7ed; border: 1px solid #ffedd5; border-radius: 8px; color: #9a3412;'>{reason}</div>",
        "Our supervisory team has been alerted to review the case and arrange additional field remediation."
    ]

    text_content = (
        f"Dear {complaint.citizen_name or 'Citizen'},\n\n"
        f"Your complaint has been REOPENED.\n"
        f"Tracking ID: {complaint.tracking_id}\n"
        f"Reason: {reason}\n\n"
        f"Track your complaint online:\n"
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5175').rstrip('/')}/track?id={complaint.tracking_id}\n"
    )

    html_content = _build_email_template(
        title=f"Complaint Reopened: {complaint.tracking_id}",
        header_badge="Case Reopened",
        body_paragraphs=body_paragraphs,
        tracking_id=complaint.tracking_id,
        action_url=None
    )

    return _send_html_email(recipient, subject, text_content, html_content, complaint, 'COMPLAINT_REOPENED', dedup_key)
