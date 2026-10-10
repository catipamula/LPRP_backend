from django.contrib import admin
from .models import (
    Department, Category, UserProfile, Complaint,
    ComplaintAttachment, ComplaintStatusHistory, ComplaintMessage,
    Notification, AuditLog, RoutingRule
)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'emergency_contact', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'default_priority', 'sla_hours', 'is_active')
    list_filter = ('department', 'default_priority', 'is_active')
    search_fields = ('name', 'code')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'ward', 'phone')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'phone', 'ward')

class ComplaintAttachmentInline(admin.TabularInline):
    model = ComplaintAttachment
    extra = 0

class ComplaintStatusHistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0

class ComplaintMessageInline(admin.TabularInline):
    model = ComplaintMessage
    extra = 0

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('tracking_id', 'title', 'department', 'priority', 'status', 'ward', 'is_overdue', 'created_at')
    list_filter = ('status', 'priority', 'department', 'is_overdue', 'created_at')
    search_fields = ('tracking_id', 'title', 'citizen_name', 'ward')
    inlines = [ComplaintAttachmentInline, ComplaintStatusHistoryInline, ComplaintMessageInline]

@admin.register(ComplaintStatusHistory)
class ComplaintStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'from_status', 'to_status', 'changed_by', 'is_internal', 'created_at')
    list_filter = ('to_status', 'is_internal')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'complaint', 'created_at')
    list_filter = ('action',)
    search_fields = ('action', 'details')

@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'department', 'priority', 'is_active')
    list_filter = ('department', 'is_active')
