"""Canonical service routing for CivicFix.

Every model-supported civic category has its own service unit.  The field-worker
accounts are provisioned two per category so the router can automatically choose
an available worker without mixing service areas.
"""

CATEGORY_DEPARTMENT = {
    "pothole": "Pothole Response",
    "garbage": "Garbage & Waste",
    "streetlight": "Streetlight Maintenance",
    "drainage": "Drainage Response",
    "road_infrastructure": "Road Infrastructure",
    "water_supply": "Water Supply",
}

DEPARTMENT_NAMES = tuple(CATEGORY_DEPARTMENT.values())
SERVICE_CATEGORIES = tuple(CATEGORY_DEPARTMENT.keys())


def department_for_category(category: str | None) -> str:
    return CATEGORY_DEPARTMENT.get(category or "", "Other / Unassigned")


def canonical_department(category: str | None) -> str:
    return department_for_category(category)


def is_routable_category(category: str | None) -> bool:
    return (category or "") in CATEGORY_DEPARTMENT
