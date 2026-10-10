from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Department, Category, UserProfile, Complaint,
    ComplaintAttachment, ComplaintStatusHistory, ComplaintMessage,
    Notification, AuditLog, RoutingRule
)

class DepartmentSerializer(serializers.ModelSerializer):
    complaint_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'code', 'name', 'description', 'icon', 'is_active', 'emergency_contact', 'complaint_count']

    def get_complaint_count(self, obj):
        return obj.complaints.count()

class CategorySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'department', 'department_name', 'code', 'name', 'description', 'default_priority', 'sla_hours', 'is_active']

class UserProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['role', 'department', 'department_name', 'ward', 'phone', 'preferred_language', 'address']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

class ComplaintAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintAttachment
        fields = ['id', 'file', 'file_url', 'file_type', 'file_name', 'file_size', 'is_resolution_proof', 'uploaded_by_name', 'created_at']

    def get_file_url(self, obj):
        if not obj.file:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

class ComplaintStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = ComplaintStatusHistory
        fields = ['id', 'from_status', 'to_status', 'changed_by_name', 'notes', 'is_internal', 'created_at']

class ComplaintMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintMessage
        fields = ['id', 'complaint', 'sender', 'sender_name', 'sender_role', 'message', 'is_read', 'created_at']
        read_only_fields = ['sender', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    tracking_id = serializers.CharField(source='complaint.tracking_id', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'tracking_id', 'title', 'message', 'notification_type', 'is_read', 'created_at']

class ComplaintListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_officer_name = serializers.CharField(source='assigned_officer.get_full_name', read_only=True)

    class Meta:
        model = Complaint
        fields = [
            'id', 'tracking_id', 'title', 'department', 'department_name', 'department_code',
            'category', 'category_name', 'custom_category', 'priority', 'status',
            'assigned_officer_name', 'state', 'city', 'locality', 'ward',
            'latitude', 'longitude', 'is_overdue', 'sla_due_date', 'created_at'
        ]

class ComplaintDetailSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_officer_name = serializers.CharField(source='assigned_officer.username', read_only=True)
    attachments = ComplaintAttachmentSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    messages = ComplaintMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Complaint
        fields = '__all__'

    def get_history(self, obj):
        # Exclude internal notes if requested by unprivileged citizen, order chronologically
        request = self.context.get('request')
        user = request.user if request else None
        is_staff = user and user.is_authenticated and hasattr(user, 'profile') and user.profile.role in ['OFFICER', 'SUPERVISOR', 'ADMIN']
        history_qs = obj.history.all().order_by('created_at')
        if not is_staff:
            history_qs = history_qs.filter(is_internal=False)
        return ComplaintStatusHistorySerializer(history_qs, many=True, context=self.context).data

class ComplaintPublicSerializer(serializers.ModelSerializer):
    """
    Sanitized complaint serializer for public issue map and citizen tracking.
    Never exposes citizen private contact info (email, phone, real name if anonymous).
    """
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_officer_name = serializers.CharField(source='assigned_officer.username', read_only=True)
    attachments = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            'id', 'tracking_id', 'title', 'description', 'department', 'department_name', 'department_code',
            'category', 'category_name', 'custom_category', 'priority', 'status',
            'assigned_officer_name', 'locality', 'ward', 'city', 'latitude', 'longitude',
            'is_overdue', 'sla_due_date', 'resolution_notes', 'rejection_reason',
            'created_at', 'updated_at', 'work_started_at', 'work_completed_at',
            'feedback_rating', 'feedback_comments', 'attachments', 'history'
        ]

    def get_attachments(self, obj):
        # Return all attachments associated with this complaint
        return ComplaintAttachmentSerializer(obj.attachments.all(), many=True, context=self.context).data

    def get_history(self, obj):
        # Exclude internal staff notes, order chronologically
        history_qs = obj.history.filter(is_internal=False).order_by('created_at')
        return ComplaintStatusHistorySerializer(history_qs, many=True, context=self.context).data

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    tracking_id = serializers.CharField(source='complaint.tracking_id', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user_name', 'action', 'tracking_id', 'ip_address', 'details', 'created_at']

class RoutingRuleSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = RoutingRule
        fields = ['id', 'keyword', 'department', 'department_name', 'priority', 'is_active']
