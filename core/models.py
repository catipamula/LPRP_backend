from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import datetime

class Department(models.Model):
    CODE_CHOICES = [
        ('MUNICIPALITY', 'Municipality / Municipal Corporation'),
        ('WARD_COUNCILLOR', 'Ward Councillor / Corporator'),
        ('PWD_ROADS', 'Public Works Department / Roads Authority'),
        ('HOUSING_BOARD', 'Housing Board / Development Authority'),
        ('FIRE', 'Fire Department'),
        ('POLICE', 'Local Police'),
        ('ELECTRICITY', 'Electricity Department'),
        ('DISASTER_MGMT', 'Disaster Management / SDRF / NDRF Coordination'),
    ]

    code = models.CharField(max_length=50, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='Building')
    is_active = models.BooleanField(default=True)
    emergency_contact = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='categories')
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    default_priority = models.CharField(
        max_length=20,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('EMERGENCY', 'Emergency')],
        default='MEDIUM'
    )
    sla_hours = models.IntegerField(default=48)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('department', 'code')

    def __str__(self):
        return f"{self.department.code} - {self.name}"

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('CITIZEN', 'Citizen'),
        ('OFFICER', 'Department Officer'),
        ('SUPERVISOR', 'Department Supervisor'),
        ('ADMIN', 'System Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CITIZEN')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')
    ward = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    preferred_language = models.CharField(max_length=10, default='en')
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

class Complaint(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('EMERGENCY', 'Emergency'),
    ]

    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('UNDER_VERIFICATION', 'Under Verification'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('REJECTED', 'Rejected'),
        ('REOPENED', 'Reopened'),
        ('ESCALATED', 'Escalated'),
    ]

    tracking_id = models.CharField(max_length=30, unique=True, db_index=True)
    citizen = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    citizen_name = models.CharField(max_length=100)
    citizen_phone = models.CharField(max_length=20, blank=True)
    citizen_email = models.EmailField(blank=True)
    is_anonymous = models.BooleanField(default=False)

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    custom_category = models.CharField(max_length=150, blank=True)

    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SUBMITTED')

    assigned_officer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_complaints')
    incident_date = models.DateTimeField(null=True, blank=True)

    # Location details
    state = models.CharField(max_length=100, default='Telangana')
    city = models.CharField(max_length=100, default='Hyderabad')
    locality = models.CharField(max_length=150, blank=True)
    street = models.CharField(max_length=150, blank=True)
    ward = models.CharField(max_length=50, blank=True)
    landmark = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    preferred_language = models.CharField(max_length=10, default='en')
    sla_due_date = models.DateTimeField(null=True, blank=True)
    is_overdue = models.BooleanField(default=False)

    # Actions & Workflow
    rejection_reason = models.TextField(blank=True)
    reopen_reason = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Feedback
    feedback_rating = models.IntegerField(null=True, blank=True) # 1 to 5
    feedback_comments = models.TextField(blank=True)

    work_started_at = models.DateTimeField(null=True, blank=True)
    work_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.tracking_id:
            random_part = uuid.uuid4().hex[:6].upper()
            year = timezone.now().year
            self.tracking_id = f"SC-{year}-{random_part}"

        # Calculate SLA if not already set
        if not self.sla_due_date:
            hours = 48
            if self.category and self.category.sla_hours:
                hours = self.category.sla_hours
            elif self.priority == 'EMERGENCY':
                hours = 6
            elif self.priority == 'HIGH':
                hours = 24
            elif self.priority == 'LOW':
                hours = 96
            self.sla_due_date = timezone.now() + datetime.timedelta(hours=hours)

        # Check overdue status
        if self.sla_due_date and timezone.now() > self.sla_due_date and self.status not in ['RESOLVED', 'CLOSED', 'REJECTED']:
            self.is_overdue = True
        else:
            self.is_overdue = False

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tracking_id} - {self.title} ({self.status})"

class ComplaintAttachment(models.Model):
    TYPE_CHOICES = [
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('DOCUMENT', 'Document'),
    ]

    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='complaint_attachments/%Y/%m/')
    file_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='IMAGE')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    is_resolution_proof = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.file_type})"

class ComplaintStatusHistory(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='history')
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    is_internal = models.BooleanField(default=False) # Internal staff note vs visible note
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complaint.tracking_id}: {self.from_status} -> {self.to_status}"

class ComplaintMessage(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=100)
    sender_role = models.CharField(max_length=20, default='CITIZEN')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Msg on {self.complaint.tracking_id} by {self.sender_name}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('ASSIGNMENT', 'Case Assigned'),
        ('ESCALATION', 'Case Escalated'),
        ('MESSAGE', 'New Message'),
        ('SLA_WARNING', 'SLA Approaching'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='STATUS_CHANGE')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    complaint = models.ForeignKey(Complaint, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"

class RoutingRule(models.Model):
    keyword = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    priority = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Keyword '{self.keyword}' -> {self.department.code}"

class EmailNotificationLog(models.Model):
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
    ]

    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='email_logs', null=True, blank=True)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    event_type = models.CharField(max_length=50)  # CREATED, STATUS_UPDATED, RESOLVED, REJECTED, REOPENED
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    dedup_key = models.CharField(max_length=200, unique=True, null=True, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.event_type} -> {self.recipient_email} [{self.status}]"

