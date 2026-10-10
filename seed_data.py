import os
import django
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (
    Department, Category, UserProfile, Complaint,
    ComplaintStatusHistory, RoutingRule, Notification
)

def run_seed():
    print("Starting database seeding...")

    # 1. Create All 8 Departments
    departments_data = [
        {
            'code': 'MUNICIPALITY',
            'name': 'Municipality / Municipal Corporation',
            'description': 'Handles garbage collection, street sanitation, drainage, sewage, waterlogging, and public cleanliness.',
            'icon': 'Trash2',
            'emergency_contact': '040-21111111'
        },
        {
            'code': 'WARD_COUNCILLOR',
            'name': 'Ward Councillor / Corporator',
            'description': 'Ward-level complaints, unresolved local community issues, multi-department coordination, and ward development.',
            'icon': 'Users',
            'emergency_contact': '040-22222222'
        },
        {
            'code': 'PWD_ROADS',
            'name': 'Public Works Department / Roads Authority',
            'description': 'Potholes, damaged roads, broken footpaths, bridges, road obstructions, and public road infrastructure.',
            'icon': 'HardHat',
            'emergency_contact': '040-23333333'
        },
        {
            'code': 'HOUSING_BOARD',
            'name': 'Housing Board / Development Authority',
            'description': 'Public housing infrastructure, unsafe buildings, government residential quarters, and urban development.',
            'icon': 'Home',
            'emergency_contact': '040-24444444'
        },
        {
            'code': 'FIRE',
            'name': 'Fire Department',
            'description': 'Fire hazards, smoke risks, fire safety compliance, emergency access blockages, and fire incident reports.',
            'icon': 'Flame',
            'emergency_contact': '101'
        },
        {
            'code': 'POLICE',
            'name': 'Local Police',
            'description': 'Public safety concerns, non-emergency hazards, traffic obstructions, unauthorized activities, and civic security.',
            'icon': 'ShieldAlert',
            'emergency_contact': '100'
        },
        {
            'code': 'ELECTRICITY',
            'name': 'Electricity Department',
            'description': 'Power outages, damaged electric poles, hanging or exposed wires, transformer faults, and supply issues.',
            'icon': 'Zap',
            'emergency_contact': '1912'
        },
        {
            'code': 'DISASTER_MGMT',
            'name': 'Disaster Management / SDRF / NDRF Coordination',
            'description': 'Flood relief, storm uprooted trees, extreme weather damage, disaster blockages, and coordinated emergency recovery.',
            'icon': 'AlertTriangle',
            'emergency_contact': '1070'
        },
    ]

    dept_objs = {}
    for data in departments_data:
        dept, created = Department.objects.get_or_create(
            code=data['code'],
            defaults=data
        )
        dept_objs[data['code']] = dept
        print(f"[{'Created' if created else 'Exists'}] Department: {dept.name}")

    # 2. Categories for each department
    categories_data = [
        # Municipality
        ('MUNICIPALITY', 'GARBAGE', 'Garbage Collection & Overflowing Bins', 'HIGH', 24),
        ('MUNICIPALITY', 'STREET_CLEAN', 'Street Cleaning & Sanitation', 'MEDIUM', 48),
        ('MUNICIPALITY', 'DRAINAGE', 'Drainage and Sewage Overflow', 'HIGH', 24),
        ('MUNICIPALITY', 'WATERLOGGING', 'Waterlogging & Stagnant Water', 'HIGH', 24),
        ('MUNICIPALITY', 'STREETLIGHT', 'Public Streetlight Maintenance', 'LOW', 72),
        ('MUNICIPALITY', 'CIVIC_CLEAN', 'Public Cleanliness & Civic Maintenance', 'MEDIUM', 48),

        # Ward Councillor
        ('WARD_COUNCILLOR', 'WARD_GENERAL', 'General Ward-Level Complaint', 'MEDIUM', 72),
        ('WARD_COUNCILLOR', 'UNRESOLVED_LOCAL', 'Unresolved Local Issues', 'HIGH', 48),
        ('WARD_COUNCILLOR', 'COMMUNITY_INFRA', 'Community Infrastructure Problems', 'MEDIUM', 96),
        ('WARD_COUNCILLOR', 'MULTI_DEPT_ESCALATION', 'Complaints Requiring Ward Coordination', 'HIGH', 36),

        # PWD / Roads
        ('PWD_ROADS', 'POTHOLE', 'Potholes & Damaged Roads', 'HIGH', 48),
        ('PWD_ROADS', 'FOOTPATH', 'Broken Footpaths & Walkways', 'MEDIUM', 72),
        ('PWD_ROADS', 'BRIDGE_DAMAGE', 'Damaged Bridges & Public Flyovers', 'EMERGENCY', 12),
        ('PWD_ROADS', 'ROAD_OBSTRUCTION', 'Road Obstructions & Unsafe Surfaces', 'HIGH', 24),
        ('PWD_ROADS', 'CONSTRUCTION_ISSUE', 'Road Construction & Maintenance Delays', 'LOW', 96),

        # Housing Board
        ('HOUSING_BOARD', 'UNSAFE_BUILDING', 'Unsafe or Damaged Public Building', 'HIGH', 36),
        ('HOUSING_BOARD', 'HOUSING_MAINT', 'Public Housing Maintenance', 'MEDIUM', 72),
        ('HOUSING_BOARD', 'DEV_INFRA', 'Development Authority Infrastructure Issues', 'MEDIUM', 96),
        ('HOUSING_BOARD', 'ILLEGAL_CONSTRUCTION', 'Construction-Related Public Property Concerns', 'HIGH', 48),

        # Fire Department
        ('FIRE', 'FIRE_HAZARD', 'Fire Hazard & Smoke Risk', 'EMERGENCY', 6),
        ('FIRE', 'SAFETY_EQUIPMENT', 'Fire Safety Equipment Non-Functional', 'HIGH', 24),
        ('FIRE', 'EMERGENCY_ACCESS_BLOCKED', 'Blocked Emergency Access / Fire Lane', 'EMERGENCY', 6),
        ('FIRE', 'PUBLIC_BUILDING_SAFETY', 'Fire Safety in Public Buildings', 'HIGH', 36),

        # Local Police
        ('POLICE', 'PUBLIC_SAFETY', 'Public Safety & Non-Emergency Hazard', 'HIGH', 12),
        ('POLICE', 'TRAFFIC_SAFETY', 'Traffic & Road Safety Hazard', 'HIGH', 12),
        ('POLICE', 'PUBLIC_OBSTRUCTION', 'Illegal Public Obstruction / Encroachment', 'MEDIUM', 48),
        ('POLICE', 'SUSPICIOUS_HAZARD', 'Suspicious Hazard Requiring Review', 'EMERGENCY', 6),

        # Electricity Department
        ('ELECTRICITY', 'POWER_OUTAGE', 'Area Power Outage / Grid Failure', 'EMERGENCY', 6),
        ('ELECTRICITY', 'DAMAGED_POLE', 'Damaged Electrical Pole', 'HIGH', 12),
        ('ELECTRICITY', 'FALLEN_WIRE', 'Fallen or Exposed Live Power Lines', 'EMERGENCY', 4),
        ('ELECTRICITY', 'STREETLIGHT_FAULT', 'Streetlight Electrical Sparking / Fault', 'MEDIUM', 24),
        ('ELECTRICITY', 'TRANSFORMER_ISSUE', 'Transformer Burning / Overload', 'EMERGENCY', 6),

        # Disaster Management
        ('DISASTER_MGMT', 'FLOODING', 'Severe Flooding & Water Rescue Needed', 'EMERGENCY', 4),
        ('DISASTER_MGMT', 'FALLEN_TREE', 'Fallen Trees After Storm Blocking Roads', 'HIGH', 12),
        ('DISASTER_MGMT', 'STORM_DAMAGE', 'Severe Weather Infrastructure Damage', 'EMERGENCY', 8),
        ('DISASTER_MGMT', 'EMERGENCY_DISASTER', 'Disaster Relief Coordination Required', 'EMERGENCY', 6),
    ]

    for dept_code, cat_code, cat_name, priority, sla in categories_data:
        dept = dept_objs.get(dept_code)
        if dept:
            cat, created = Category.objects.get_or_create(
                department=dept,
                code=cat_code,
                defaults={
                    'name': cat_name,
                    'default_priority': priority,
                    'sla_hours': sla
                }
            )

    print("Categories seeded successfully.")

    # 3. Create Default Users
    # Admin
    admin_user, created = User.objects.get_or_create(username='admin', defaults={
        'email': 'admin@smartcity.gov.in',
        'first_name': 'Super',
        'last_name': 'Administrator',
        'is_staff': True,
        'is_superuser': True
    })
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
    admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user, defaults={
        'role': 'ADMIN',
        'phone': '9876543210'
    })

    # Department Officers
    officers = [
        ('officer_muni', 'Municipality', 'Officer', 'MUNICIPALITY'),
        ('officer_pwd', 'PWD Roads', 'Officer', 'PWD_ROADS'),
        ('officer_elec', 'Electricity', 'Officer', 'ELECTRICITY'),
        ('officer_police', 'Police', 'Officer', 'POLICE'),
        ('officer_fire', 'Fire', 'Officer', 'FIRE'),
        ('officer_disaster', 'Disaster', 'Officer', 'DISASTER_MGMT'),
    ]

    officer_objs = {}
    for uname, fname, lname, dcode in officers:
        u, u_created = User.objects.get_or_create(username=uname, defaults={
            'email': f'{uname}@smartcity.gov.in',
            'first_name': fname,
            'last_name': lname,
            'is_staff': True
        })
        if u_created:
            u.set_password('pass123')
            u.save()
        prof, _ = UserProfile.objects.get_or_create(user=u, defaults={
            'role': 'OFFICER',
            'department': dept_objs.get(dcode),
            'phone': '9888800000'
        })
        officer_objs[dcode] = u

    # Demo Citizen
    citizen_user, c_created = User.objects.get_or_create(username='citizen', defaults={
        'email': 'citizen@example.com',
        'first_name': 'Ramesh',
        'last_name': 'Kumar'
    })
    if c_created:
        citizen_user.set_password('pass123')
        citizen_user.save()
    UserProfile.objects.get_or_create(user=citizen_user, defaults={
        'role': 'CITIZEN',
        'ward': 'Ward 12 - Banjara Hills',
        'phone': '9944332211',
        'preferred_language': 'en'
    })

    print("Users & profiles seeded successfully.")

    # 4. Sample Seed Complaints for Demonstrations
    sample_complaints = [
        {
            'tracking_id': 'SC-2026-A10982',
            'title': 'Deep hazardous pothole near Jubilee Hills Checkpost',
            'description': 'A wide crater in the road right after the traffic signal is causing serious vehicular damage and traffic slowdown.',
            'department': dept_objs['PWD_ROADS'],
            'priority': 'HIGH',
            'status': 'IN_PROGRESS',
            'ward': 'Ward 10 - Jubilee Hills',
            'locality': 'Road No. 36',
            'latitude': 17.4319,
            'longitude': 78.4073,
            'citizen': citizen_user,
            'citizen_name': 'Ramesh Kumar',
            'citizen_phone': '9944332211',
            'assigned_officer': officer_objs.get('PWD_ROADS'),
            'work_started_at': timezone.now() - datetime.timedelta(hours=5),
        },
        {
            'tracking_id': 'SC-2026-B44910',
            'title': 'Overflowing municipal garbage container on Main Street',
            'description': 'The community garbage bins have not been cleared for three days. Waste is spilling onto the pedestrian footpath.',
            'department': dept_objs['MUNICIPALITY'],
            'priority': 'MEDIUM',
            'status': 'RESOLVED',
            'ward': 'Ward 14 - Madhapur',
            'locality': 'Ayyappa Society',
            'latitude': 17.4483,
            'longitude': 78.3915,
            'citizen': citizen_user,
            'citizen_name': 'Ramesh Kumar',
            'citizen_phone': '9944332211',
            'assigned_officer': officer_objs.get('MUNICIPALITY'),
            'work_started_at': timezone.now() - datetime.timedelta(days=1),
            'work_completed_at': timezone.now() - datetime.timedelta(hours=2),
            'resolution_notes': 'Sanitation crew dispatched with compacting truck. Area thoroughly disinfected.',
            'feedback_rating': 5,
            'feedback_comments': 'Prompt cleanup, thank you very much!',
        },
        {
            'tracking_id': 'SC-2026-C88721',
            'title': 'Fallen live wire sparking near primary school',
            'description': 'Heavy winds knocked down a service wire from the utility pole. It is hanging loose near the footpath.',
            'department': dept_objs['ELECTRICITY'],
            'priority': 'EMERGENCY',
            'status': 'ASSIGNED',
            'ward': 'Ward 18 - Gachibowli',
            'locality': 'Telecom Nagar',
            'latitude': 17.4401,
            'longitude': 78.3489,
            'citizen': None,
            'citizen_name': 'Pooja Reddy',
            'citizen_phone': '9777665544',
            'assigned_officer': officer_objs.get('ELECTRICITY'),
        },
        {
            'tracking_id': 'SC-2026-D32190',
            'title': 'Severe waterlogging blocking underpass after thunderstorm',
            'description': 'Underpass completely submerged with 3 feet of water, two cars stalled.',
            'department': dept_objs['DISASTER_MGMT'],
            'priority': 'EMERGENCY',
            'status': 'ESCALATED',
            'ward': 'Ward 08 - Begumpet',
            'locality': 'Rasoolpura Underpass',
            'latitude': 17.4442,
            'longitude': 78.4735,
            'citizen': citizen_user,
            'citizen_name': 'Ramesh Kumar',
            'citizen_phone': '9944332211',
            'assigned_officer': officer_objs.get('DISASTER_MGMT'),
        },
        {
            'tracking_id': 'SC-2026-E55122',
            'title': 'Unregistered construction debris dumping on public ground',
            'description': 'Trucks unloading heavy concrete slabs on public park premises during nighttime.',
            'department': None, # Unrouted - For Review Queue demonstration!
            'priority': 'MEDIUM',
            'status': 'UNDER_VERIFICATION',
            'ward': 'Ward 05 - Ameerpet',
            'locality': 'Sanjeeva Reddy Nagar',
            'latitude': 17.4375,
            'longitude': 78.4482,
            'citizen': None,
            'citizen_name': 'Sunil Verma',
            'citizen_phone': '9555112233',
        }
    ]

    for comp_data in sample_complaints:
        tid = comp_data['tracking_id']
        if not Complaint.objects.filter(tracking_id=tid).exists():
            c = Complaint.objects.create(**comp_data)
            # Create status history
            ComplaintStatusHistory.objects.create(
                complaint=c,
                from_status='NONE',
                to_status=c.status,
                notes=f'Initial sample status for {c.tracking_id}'
            )

    print("Sample complaints seeded successfully!")
    print("\nCredentials for testing:")
    print("---------------------------------------------")
    print("Admin:        admin / admin123")
    print("Citizen:      citizen / pass123")
    print("Muni Officer: officer_muni / pass123")
    print("PWD Officer:  officer_pwd / pass123")
    print("Elec Officer: officer_elec / pass123")
    print("---------------------------------------------")

if __name__ == '__main__':
    run_seed()
