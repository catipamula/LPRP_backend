from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Count, Avg, F, Q
from django.utils import timezone
from django.http import HttpResponse
import csv
import datetime
import urllib.request
import urllib.parse
import json
from django.db import transaction

from .models import (
    Department, Category, UserProfile, Complaint,
    ComplaintAttachment, ComplaintStatusHistory, ComplaintMessage,
    Notification, AuditLog, RoutingRule, EmailNotificationLog
)
from .serializers import (
    DepartmentSerializer, CategorySerializer, UserSerializer,
    UserProfileSerializer, ComplaintListSerializer, ComplaintDetailSerializer,
    ComplaintPublicSerializer, ComplaintAttachmentSerializer,
    ComplaintMessageSerializer, NotificationSerializer, AuditLogSerializer,
    RoutingRuleSerializer
)
from .routing import determine_department_route
from .notifications import create_and_send_notification
from .email_service import (
    send_complaint_created_email,
    send_status_updated_email,
    send_complaint_resolved_email,
    send_complaint_rejected_email,
    send_complaint_reopened_email
)


class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        phone = request.data.get('phone', '').strip()
        preferred_language = request.data.get('preferred_language', 'en')
        role = request.data.get('role', 'CITIZEN')
        department_id = request.data.get('department_id', None)

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        dept = None
        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                pass

        profile = UserProfile.objects.create(
            user=user,
            role=role if role in ['CITIZEN', 'OFFICER', 'SUPERVISOR', 'ADMIN'] else 'CITIZEN',
            department=dept,
            phone=phone,
            preferred_language=preferred_language
        )

        token, _ = Token.objects.get_or_create(user=user)
        AuditLog.objects.create(user=user, action='USER_REGISTERED', details=f"Role: {profile.role}")

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        # Ensure profile exists
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user, role='ADMIN' if user.is_superuser else 'CITIZEN')

        AuditLog.objects.create(user=user, action='USER_LOGGED_IN', ip_address=request.META.get('REMOTE_ADDR', ''))

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class UserProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        user = request.user
        profile = user.profile
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.email = request.data.get('email', user.email)
        user.save()

        profile.phone = request.data.get('phone', profile.phone)
        profile.preferred_language = request.data.get('preferred_language', profile.preferred_language)
        profile.ward = request.data.get('ward', profile.ward)
        profile.address = request.data.get('address', profile.address)
        profile.save()

        return Response(UserSerializer(user).data)


class DepartmentListView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Allow admins to see inactive, others see active only
        if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN':
            depts = Department.objects.all().order_by('id')
        else:
            depts = Department.objects.filter(is_active=True).order_by('id')
        return Response(DepartmentSerializer(depts, many=True).data)

    def post(self, request):
        if not (request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DepartmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryListView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        dept_id = request.query_params.get('department_id')
        qs = Category.objects.filter(is_active=True)
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return Response(CategorySerializer(qs, many=True).data)


class ComplaintCreateView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        priority = data.get('priority', 'MEDIUM').upper()
        department_id = data.get('department_id') or None
        category_id = data.get('category_id') or None
        custom_category = data.get('custom_category', '').strip()

        citizen_name = data.get('citizen_name', '').strip()
        citizen_phone = data.get('citizen_phone', '').strip()
        citizen_email = data.get('citizen_email', '').strip()
        is_anonymous = data.get('is_anonymous', 'false').lower() in ['true', '1']

        state = data.get('state', 'Telangana')
        city = data.get('city', 'Hyderabad')
        locality = data.get('locality', '').strip()
        street = data.get('street', '').strip()
        ward = data.get('ward', '').strip()
        landmark = data.get('landmark', '').strip()
        preferred_language = data.get('preferred_language', 'en')

        latitude = data.get('latitude') or None
        longitude = data.get('longitude') or None
        incident_date = data.get('incident_date') or None

        if not title or not description:
            return Response({'error': 'Title and description are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Authenticated citizen context if available
        user = request.user if request.user.is_authenticated else None
        if user and not citizen_name:
            citizen_name = user.get_full_name() or user.username
        if user and not citizen_email:
            citizen_email = user.email

        if not citizen_name:
            citizen_name = 'Anonymous Citizen' if is_anonymous else 'Resident'

        # Resolve category if provided
        category_obj = None
        if category_id:
            try:
                category_obj = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        # Rule-based routing
        dept_obj = determine_department_route(
            title=title,
            description=description,
            selected_dept_id=department_id,
            category=category_obj
        )

        with transaction.atomic():
            complaint = Complaint.objects.create(
                citizen=user,
                citizen_name=citizen_name,
                citizen_phone=citizen_phone,
                citizen_email=citizen_email,
                is_anonymous=is_anonymous,
                department=dept_obj,
                category=category_obj,
                custom_category=custom_category,
                title=title,
                description=description,
                priority=priority if priority in ['LOW', 'MEDIUM', 'HIGH', 'EMERGENCY'] else 'MEDIUM',
                status='SUBMITTED' if dept_obj else 'UNDER_VERIFICATION',
                state=state,
                city=city,
                locality=locality,
                street=street,
                ward=ward,
                landmark=landmark,
                latitude=latitude,
                longitude=longitude,
                incident_date=incident_date,
                preferred_language=preferred_language
            )

            # Initial history record
            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                from_status='NONE',
                to_status=complaint.status,
                changed_by=user,
                notes='Complaint submitted by citizen.',
                is_internal=False
            )

            # Handle file attachments
            files = request.FILES.getlist('attachments')
            for f in files:
                file_name = f.name
                size = f.size
                content_type = f.content_type.lower()
                file_type = 'DOCUMENT'
                if 'image' in content_type:
                    file_type = 'IMAGE'
                elif 'video' in content_type:
                    file_type = 'VIDEO'

                ComplaintAttachment.objects.create(
                    complaint=complaint,
                    file=f,
                    file_type=file_type,
                    file_name=file_name,
                    file_size=size,
                    uploaded_by=user
                )

            # Dispatch in-app notification
            if user:
                create_and_send_notification(
                    user=user,
                    complaint=complaint,
                    title="Complaint Submitted Successfully",
                    message=f"Your complaint '{complaint.title}' has been registered with ID {complaint.tracking_id}."
                )

            AuditLog.objects.create(
                user=user,
                complaint=complaint,
                action='COMPLAINT_CREATED',
                details=f"Tracking ID: {complaint.tracking_id}, Dept: {dept_obj.name if dept_obj else 'Review Queue'}"
            )

            # Send Email Confirmation upon successful database commit
            transaction.on_commit(lambda: send_complaint_created_email(complaint))

        return Response({
            'message': 'Complaint submitted successfully',
            'tracking_id': complaint.tracking_id,
            'complaint': ComplaintDetailSerializer(complaint, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)

class ComplaintTrackView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, tracking_id):
        try:
            complaint = Complaint.objects.get(tracking_id__iexact=tracking_id.strip())
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint with tracking ID not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check and update overdue status dynamically
        if complaint.sla_due_date and complaint.status not in ['RESOLVED', 'CLOSED', 'REJECTED']:
            if timezone.now() > complaint.sla_due_date and not complaint.is_overdue:
                complaint.is_overdue = True
                complaint.save(update_fields=['is_overdue'])

        # If citizen is the owner or staff, provide full details, otherwise sanitized public details
        user = request.user if request.user.is_authenticated else None
        is_owner = user and complaint.citizen == user
        is_staff = user and hasattr(user, 'profile') and user.profile.role in ['OFFICER', 'SUPERVISOR', 'ADMIN']

        if is_owner or is_staff:
            serializer = ComplaintDetailSerializer(complaint, context={'request': request})
        else:
            serializer = ComplaintPublicSerializer(complaint, context={'request': request})

        response = Response(serializer.data)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


class CitizenComplaintsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        complaints = Complaint.objects.filter(citizen=request.user).order_by('-created_at')
        return Response(ComplaintListSerializer(complaints, many=True, context={'request': request}).data)


class OfficerDepartmentComplaintsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role not in ['OFFICER', 'SUPERVISOR', 'ADMIN']:
            return Response({'error': 'Unauthorized. Staff privileges required.'}, status=status.HTTP_403_FORBIDDEN)

        qs = Complaint.objects.all().order_by('-created_at')

        # Officers are restricted to their department, unless assigned to them or supervisor
        if user.profile.role == 'OFFICER' and user.profile.department:
            qs = qs.filter(Q(department=user.profile.department) | Q(assigned_officer=user))
        elif user.profile.role == 'SUPERVISOR' and user.profile.department:
            qs = qs.filter(department=user.profile.department)

        # Filters
        dept_id = request.query_params.get('department_id')
        if dept_id and user.profile.role == 'ADMIN':
            qs = qs.filter(department_id=dept_id)

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())

        priority = request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority.upper())

        ward = request.query_params.get('ward')
        if ward:
            qs = qs.filter(ward__icontains=ward)

        overdue = request.query_params.get('overdue')
        if overdue == 'true':
            qs = qs.filter(is_overdue=True)

        return Response(ComplaintListSerializer(qs, many=True, context={'request': request}).data)


class ComplaintDetailView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        is_owner = user and complaint.citizen == user
        is_staff = user and hasattr(user, 'profile') and user.profile.role in ['OFFICER', 'SUPERVISOR', 'ADMIN']

        if is_staff:
            # Check if officer is authorized for this complaint
            if user.profile.role in ['OFFICER', 'SUPERVISOR']:
                if user.profile.department and complaint.department:
                    if complaint.department != user.profile.department and complaint.assigned_officer != user and user.profile.role != 'SUPERVISOR':
                        return Response({'error': 'Access denied to complaints from another department.'}, status=status.HTTP_403_FORBIDDEN)
            return Response(ComplaintDetailSerializer(complaint, context={'request': request}).data)

        if is_owner:
            return Response(ComplaintDetailSerializer(complaint, context={'request': request}).data)

        # Sanitized public view
        return Response(ComplaintPublicSerializer(complaint, context={'request': request}).data)


class ComplaintStatusUpdateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role not in ['OFFICER', 'SUPERVISOR', 'ADMIN']:
            return Response({'error': 'Unauthorized. Staff privileges required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Department authorization check
        if user.profile.role in ['OFFICER', 'SUPERVISOR'] and user.profile.department and complaint.department:
            if complaint.department != user.profile.department and complaint.assigned_officer != user and user.profile.role != 'SUPERVISOR':
                return Response({'error': 'Cannot update complaints from another department.'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status', '').upper().strip()
        notes = request.data.get('notes', '').strip()
        
        # Robust boolean parsing for FormData
        is_internal_val = request.data.get('is_internal', False)
        is_internal = str(is_internal_val).lower() in ['true', '1', 'yes']

        rejection_reason = request.data.get('rejection_reason', '').strip()
        resolution_notes = request.data.get('resolution_notes', '').strip()
        assigned_officer_id = request.data.get('assigned_officer_id')

        if not new_status:
            new_status = complaint.status

        if new_status not in dict(Complaint.STATUS_CHOICES):
            return Response({'error': f'Invalid status: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from_status = complaint.status
            complaint.status = new_status

            if new_status == 'IN_PROGRESS' and not complaint.work_started_at:
                complaint.work_started_at = timezone.now()

            if new_status in ['RESOLVED', 'CLOSED']:
                if not complaint.work_completed_at:
                    complaint.work_completed_at = timezone.now()
                complaint.resolution_notes = resolution_notes or notes or complaint.resolution_notes

            if new_status == 'REJECTED':
                complaint.rejection_reason = rejection_reason or notes or complaint.rejection_reason

            # Handle assignment / reassignment
            if assigned_officer_id:
                if assigned_officer_id == 'me':
                    complaint.assigned_officer = user
                elif str(assigned_officer_id).isdigit():
                    try:
                        assigned_user = User.objects.get(id=int(assigned_officer_id))
                        complaint.assigned_officer = assigned_user
                    except User.DoesNotExist:
                        pass
                elif assigned_officer_id == 'none' or assigned_officer_id == '':
                    complaint.assigned_officer = None

            # Automatically transition to ASSIGNED if assigned and was SUBMITTED or UNDER_VERIFICATION
            if complaint.assigned_officer and from_status in ['SUBMITTED', 'UNDER_VERIFICATION'] and new_status == from_status:
                complaint.status = 'ASSIGNED'
                new_status = 'ASSIGNED'

            complaint.save()

            # Handle resolution proof attachment if uploaded
            files = request.FILES.getlist('resolution_files')
            for f in files:
                ComplaintAttachment.objects.create(
                    complaint=complaint,
                    file=f,
                    file_type='IMAGE' if 'image' in f.content_type.lower() else 'DOCUMENT',
                    file_name=f.name,
                    file_size=f.size,
                    is_resolution_proof=True,
                    uploaded_by=user
                )

            # Log status transition
            transition_notes = notes or rejection_reason or resolution_notes or f"Status changed to {new_status}."
            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                from_status=from_status,
                to_status=new_status,
                changed_by=user,
                notes=transition_notes,
                is_internal=is_internal
            )

            # Notify citizen
            if complaint.citizen:
                create_and_send_notification(
                    user=complaint.citizen,
                    complaint=complaint,
                    title=f"Complaint Status: {complaint.get_status_display()}",
                    message=f"Status of complaint {complaint.tracking_id} updated to {complaint.get_status_display()}."
                )

            AuditLog.objects.create(
                user=user,
                complaint=complaint,
                action='STATUS_UPDATED',
                details=f"From {from_status} to {new_status}. Assigned: {complaint.assigned_officer_id}. Internal: {is_internal}."
            )

            # Trigger email notification upon database transaction commit
            if new_status == 'RESOLVED':
                transaction.on_commit(lambda: send_complaint_resolved_email(complaint, resolution_notes))
            elif new_status == 'REJECTED':
                transaction.on_commit(lambda: send_complaint_rejected_email(complaint, rejection_reason))
            elif new_status != from_status:
                transaction.on_commit(lambda: send_status_updated_email(complaint, from_status, new_status, notes))

        return Response(ComplaintDetailSerializer(complaint, context={'request': request}).data)


class OfficerListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role not in ['OFFICER', 'SUPERVISOR', 'ADMIN']:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

        dept_id = request.query_params.get('department_id') or (user.profile.department_id if user.profile.role != 'ADMIN' else None)
        qs = User.objects.filter(profile__role__in=['OFFICER', 'SUPERVISOR']).select_related('profile', 'profile__department')
        if dept_id:
            qs = qs.filter(profile__department_id=dept_id)

        data = [{
            'id': u.id,
            'username': u.username,
            'full_name': u.get_full_name() or u.username,
            'role': u.profile.role,
            'department_id': u.profile.department_id,
            'department_name': u.profile.department.name if u.profile.department else 'General'
        } for u in qs]
        return Response(data)


class ComplaintReopenView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        if complaint.citizen != request.user and not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Only the complaint submitter can reopen this complaint.'}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'Reopen reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from_status = complaint.status
            complaint.status = 'REOPENED'
            complaint.reopen_reason = reason
            complaint.save()

            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                from_status=from_status,
                to_status='REOPENED',
                changed_by=request.user,
                notes=f"Reopened by citizen. Reason: {reason}",
                is_internal=False
            )

            AuditLog.objects.create(
                user=request.user,
                complaint=complaint,
                action='COMPLAINT_REOPENED',
                details=reason
            )

            transaction.on_commit(lambda: send_complaint_reopened_email(complaint, reason))

        return Response(ComplaintDetailSerializer(complaint, context={'request': request}).data)


class ComplaintFeedbackView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        if complaint.citizen != request.user:
            return Response({'error': 'Only the complaint author can submit feedback.'}, status=status.HTTP_403_FORBIDDEN)

        rating = request.data.get('rating')
        comments = request.data.get('comments', '').strip()

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError()
        except (TypeError, ValueError):
            return Response({'error': 'Rating must be an integer between 1 and 5.'}, status=status.HTTP_400_BAD_REQUEST)

        complaint.feedback_rating = rating
        complaint.feedback_comments = comments
        # Auto-close after feedback if resolved
        if complaint.status == 'RESOLVED':
            complaint.status = 'CLOSED'
            ComplaintStatusHistory.objects.create(
                complaint=complaint,
                from_status='RESOLVED',
                to_status='CLOSED',
                changed_by=request.user,
                notes=f"Citizen confirmed resolution and rated {rating}/5 stars.",
                is_internal=False
            )
        complaint.save()

        AuditLog.objects.create(
            user=request.user,
            complaint=complaint,
            action='FEEDBACK_SUBMITTED',
            details=f"Rating: {rating}/5, Comments: {comments}"
        )

        return Response({'message': 'Thank you for your feedback!'})


class ComplaintMessageView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner = complaint.citizen == user
        is_staff = hasattr(user, 'profile') and user.profile.role in ['OFFICER', 'SUPERVISOR', 'ADMIN']

        if not (is_owner or is_staff):
            return Response({'error': 'Unauthorized to view messages on this complaint.'}, status=status.HTTP_403_FORBIDDEN)

        # Mark unread messages as read
        complaint.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)

        return Response(ComplaintMessageSerializer(complaint.messages.all(), many=True).data)

    def post(self, request, pk):
        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner = complaint.citizen == user
        is_staff = hasattr(user, 'profile') and user.profile.role in ['OFFICER', 'SUPERVISOR', 'ADMIN']

        if not (is_owner or is_staff):
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

        msg_text = request.data.get('message', '').strip()
        if not msg_text:
            return Response({'error': 'Message content is required.'}, status=status.HTTP_400_BAD_REQUEST)

        role = user.profile.role if hasattr(user, 'profile') else 'CITIZEN'

        message = ComplaintMessage.objects.create(
            complaint=complaint,
            sender=user,
            sender_name=user.get_full_name() or user.username,
            sender_role=role,
            message=msg_text
        )

        # Notify the other party
        if is_owner and complaint.assigned_officer:
            create_and_send_notification(
                user=complaint.assigned_officer,
                complaint=complaint,
                title="Citizen Message Received",
                message=f"Citizen wrote on complaint {complaint.tracking_id}: '{msg_text[:60]}...'"
            )
        elif is_staff and complaint.citizen:
            create_and_send_notification(
                user=complaint.citizen,
                complaint=complaint,
                title="Department Officer Message Received",
                message=f"Department staff replied on complaint {complaint.tracking_id}: '{msg_text[:60]}...'"
            )

        return Response(ComplaintMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class PublicIssueMapView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Complaint.objects.filter(latitude__isnull=False, longitude__isnull=False)

        dept_id = request.query_params.get('department_id')
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())

        ward = request.query_params.get('ward')
        if ward:
            qs = qs.filter(ward__icontains=ward)

        return Response(ComplaintPublicSerializer(qs, many=True).data)


class NotificationListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = request.user.notifications.all()[:50]
        return Response(NotificationSerializer(notifications, many=True).data)

    def post(self, request):
        # Mark all as read
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return Response({'message': 'All notifications marked as read.'})


class AdminDashboardMetricsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        total = Complaint.objects.count()
        submitted = Complaint.objects.filter(status='SUBMITTED').count()
        verification = Complaint.objects.filter(status='UNDER_VERIFICATION').count()
        assigned = Complaint.objects.filter(status='ASSIGNED').count()
        in_progress = Complaint.objects.filter(status='IN_PROGRESS').count()
        resolved = Complaint.objects.filter(status='RESOLVED').count()
        closed = Complaint.objects.filter(status='CLOSED').count()
        reopened = Complaint.objects.filter(status='REOPENED').count()
        escalated = Complaint.objects.filter(status='ESCALATED').count()
        rejected = Complaint.objects.filter(status='REJECTED').count()
        overdue = Complaint.objects.filter(is_overdue=True).count()

        dept_stats = Department.objects.annotate(
            total=Count('complaints'),
            pending=Count('complaints', filter=~Q(complaints__status__in=['RESOLVED', 'CLOSED', 'REJECTED'])),
            resolved_count=Count('complaints', filter=Q(complaints__status__in=['RESOLVED', 'CLOSED']))
        ).values('id', 'name', 'code', 'total', 'pending', 'resolved_count')

        ward_stats = Complaint.objects.exclude(ward='').values('ward').annotate(total=Count('id')).order_by('-total')[:10]
        category_stats = Category.objects.annotate(total=Count('complaints')).values('id', 'name', 'total').order_by('-total')[:10]

        return Response({
            'overview': {
                'total': total,
                'submitted': submitted,
                'under_verification': verification,
                'assigned': assigned,
                'in_progress': in_progress,
                'resolved': resolved,
                'closed': closed,
                'reopened': reopened,
                'escalated': escalated,
                'rejected': rejected,
                'overdue': overdue,
            },
            'departments': dept_stats,
            'top_wards': ward_stats,
            'top_categories': category_stats
        })


class AdminReviewQueueView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        # Unrouted complaints or under verification
        qs = Complaint.objects.filter(Q(department__isnull=True) | Q(status='UNDER_VERIFICATION')).order_by('-created_at')
        return Response(ComplaintListSerializer(qs, many=True).data)

    def post(self, request, pk):
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            complaint = Complaint.objects.get(pk=pk)
        except Complaint.DoesNotExist:
            return Response({'error': 'Complaint not found.'}, status=status.HTTP_404_NOT_FOUND)

        dept_id = request.data.get('department_id')
        notes = request.data.get('notes', 'Routed by administrator.')

        try:
            dept = Department.objects.get(id=dept_id)
        except Department.DoesNotExist:
            return Response({'error': 'Department does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        old_dept = complaint.department.name if complaint.department else 'Unassigned'
        complaint.department = dept
        complaint.status = 'ASSIGNED'
        complaint.save()

        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            from_status='UNDER_VERIFICATION',
            to_status='ASSIGNED',
            changed_by=request.user,
            notes=f"Assigned to {dept.name}. Note: {notes}",
            is_internal=False
        )

        AuditLog.objects.create(
            user=request.user,
            complaint=complaint,
            action='DEPARTMENT_REASSIGNED',
            details=f"From {old_dept} to {dept.name}"
        )

        return Response({'message': f'Complaint successfully routed to {dept.name}.'})


class AdminAuditLogsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        logs = AuditLog.objects.all()[:100]
        return Response(AuditLogSerializer(logs, many=True).data)


class AdminExportCSVView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
            return Response({'error': 'Admin permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="complaints_export_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Tracking ID', 'Title', 'Department', 'Category', 'Priority', 'Status', 'Ward', 'Citizen Name', 'Overdue', 'Created At'])

        for c in Complaint.objects.all().order_by('-created_at'):
            writer.writerow([
                c.tracking_id,
                c.title,
                c.department.name if c.department else 'Unassigned',
                c.category.name if c.category else (c.custom_category or 'Other'),
                c.priority,
                c.status,
                c.ward,
                c.citizen_name,
                'Yes' if c.is_overdue else 'No',
                c.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response


class GeocodingSearchView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 2:
            return Response([])

        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&addressdetails=1&limit=6&countrycodes=in"
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'SmartCityCivicPortal/1.0 (contact@smartcity.gov.in)',
                    'Accept-Language': 'en'
                }
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                raw_data = json.loads(response.read().decode('utf-8'))

            results = []
            for item in raw_data:
                addr = item.get('address', {})
                results.append({
                    'display_name': item.get('display_name', ''),
                    'lat': item.get('lat', ''),
                    'lon': item.get('lon', ''),
                    'locality': addr.get('suburb') or addr.get('neighbourhood') or addr.get('residential') or addr.get('road', ''),
                    'road': addr.get('road', ''),
                    'ward': addr.get('suburb') or addr.get('city_district', ''),
                    'city': addr.get('city') or addr.get('town') or addr.get('state_district', 'Hyderabad'),
                    'state': addr.get('state', 'Telangana'),
                    'postcode': addr.get('postcode', '')
                })
            return Response(results)
        except Exception:
            return Response([])


class GeocodingReverseView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        if not lat or not lon:
            return Response({'error': 'lat and lon parameters are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'SmartCityCivicPortal/1.0 (contact@smartcity.gov.in)',
                    'Accept-Language': 'en'
                }
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

            addr = data.get('address', {})
            return Response({
                'display_name': data.get('display_name', ''),
                'locality': addr.get('suburb') or addr.get('neighbourhood') or addr.get('residential') or addr.get('road', ''),
                'road': addr.get('road', ''),
                'ward': addr.get('suburb') or addr.get('city_district', ''),
                'city': addr.get('city') or addr.get('town') or addr.get('state_district', 'Hyderabad'),
                'state': addr.get('state', 'Telangana'),
                'postcode': addr.get('postcode', '')
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_200_OK)

