from django.urls import path
from .views import (
    RegisterView, LoginView, UserProfileView,
    DepartmentListView, CategoryListView,
    ComplaintCreateView, ComplaintTrackView, CitizenComplaintsView,
    OfficerDepartmentComplaintsView, ComplaintDetailView,
    ComplaintStatusUpdateView, ComplaintReopenView, ComplaintFeedbackView,
    ComplaintMessageView, PublicIssueMapView, NotificationListView,
    AdminDashboardMetricsView, AdminReviewQueueView, AdminAuditLogsView,
    AdminExportCSVView, OfficerListView,
    GeocodingSearchView, GeocodingReverseView
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/profile/', UserProfileView.as_view(), name='auth-profile'),

    # Departments & Categories
    path('departments/', DepartmentListView.as_view(), name='departments-list'),
    path('categories/', CategoryListView.as_view(), name='categories-list'),
    path('officers/', OfficerListView.as_view(), name='officers-list'),

    # Complaints
    path('complaints/', ComplaintCreateView.as_view(), name='complaints-create'),
    path('complaints/track/<str:tracking_id>/', ComplaintTrackView.as_view(), name='complaints-track'),
    path('complaints/my/', CitizenComplaintsView.as_view(), name='complaints-my'),
    path('complaints/officer/', OfficerDepartmentComplaintsView.as_view(), name='complaints-officer'),
    path('complaints/<int:pk>/', ComplaintDetailView.as_view(), name='complaints-detail'),
    path('complaints/<int:pk>/status/', ComplaintStatusUpdateView.as_view(), name='complaints-status-update'),
    path('complaints/<int:pk>/reopen/', ComplaintReopenView.as_view(), name='complaints-reopen'),
    path('complaints/<int:pk>/feedback/', ComplaintFeedbackView.as_view(), name='complaints-feedback'),
    path('complaints/<int:pk>/messages/', ComplaintMessageView.as_view(), name='complaints-messages'),

    # Public Map & Geocoding
    path('public/map/', PublicIssueMapView.as_view(), name='public-map'),
    path('geo/search/', GeocodingSearchView.as_view(), name='geo-search'),
    path('geo/reverse/', GeocodingReverseView.as_view(), name='geo-reverse'),

    # Notifications
    path('notifications/', NotificationListView.as_view(), name='notifications-list'),

    # Admin Dashboard
    path('admin/metrics/', AdminDashboardMetricsView.as_view(), name='admin-metrics'),
    path('admin/review-queue/', AdminReviewQueueView.as_view(), name='admin-review-queue'),
    path('admin/review-queue/<int:pk>/', AdminReviewQueueView.as_view(), name='admin-review-queue-detail'),
    path('admin/audit-logs/', AdminAuditLogsView.as_view(), name='admin-audit-logs'),
    path('admin/export-csv/', AdminExportCSVView.as_view(), name='admin-export-csv'),
]
