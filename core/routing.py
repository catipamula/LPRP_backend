from .models import Department, RoutingRule

# Predefined keyword mappings to the 8 departments
KEYWORD_MAPPINGS = {
    'MUNICIPALITY': ['garbage', 'trash', 'dustbin', 'cleaning', 'sanitation', 'drainage', 'sewage', 'waterlogging', 'stagnant', 'streetlight', 'cleanliness'],
    'WARD_COUNCILLOR': ['ward', 'corporator', 'community', 'unresolved', 'coordination', 'local issue', 'escalation'],
    'PWD_ROADS': ['pothole', 'road', 'footpath', 'bridge', 'pavement', 'highway', 'tar', 'concrete', 'asphalt', 'divider', 'sidewalk'],
    'HOUSING_BOARD': ['housing', 'building', 'public building', 'construction', 'development authority', 'unsafe structure', 'slum clearance'],
    'FIRE': ['fire', 'smoke', 'fire hazard', 'extinguisher', 'emergency access', 'blaze', 'short circuit fire', 'flame'],
    'POLICE': ['police', 'crime', 'theft', 'traffic obstruction', 'public safety', 'suspicious', 'harassment', 'noise pollution', 'law and order', 'patrol'],
    'ELECTRICITY': ['power', 'electricity', 'transformer', 'power line', 'electric pole', 'blackout', 'power cut', 'wire', 'exposed wire', 'voltage'],
    'DISASTER_MGMT': ['flood', 'disaster', 'cyclone', 'storm', 'fallen tree', 'sdrf', 'ndrf', 'heavy rain', 'earthquake', 'landslide', 'emergency blockage'],
}

def determine_department_route(title, description, selected_dept_id=None, category=None):
    """
    Rule-based department routing engine without AI.
    1. If user explicitly selected a department, prioritize it.
    2. If category belongs to a department, use that department.
    3. If 'Other' or unknown, scan title and description keywords against dictionary and active RoutingRule db records.
    4. If still indeterminate, route to review queue (return None or MUNICIPALITY as fallback).
    """
    if selected_dept_id:
        try:
            return Department.objects.get(id=selected_dept_id)
        except Department.DoesNotExist:
            pass

    if category and category.department:
        return category.department

    text = f"{title} {description}".lower()

    # Check database routing rules first
    db_rules = RoutingRule.objects.filter(is_active=True).order_by('-priority')
    for rule in db_rules:
        if rule.keyword.lower() in text:
            return rule.department

    # Check predefined keyword mappings
    for code, keywords in KEYWORD_MAPPINGS.items():
        for kw in keywords:
            if kw in text:
                try:
                    return Department.objects.get(code=code)
                except Department.DoesNotExist:
                    continue

    # Return None if it requires review queue
    return None
