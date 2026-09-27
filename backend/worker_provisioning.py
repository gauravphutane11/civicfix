"""Provisioning catalog for CivicFix demo/admin deployment.

These are deterministic demo credentials so the hackathon deployment can be
bootstrapped without a manual account-creation step. Change them before any
real production deployment and keep real passwords in a secrets manager.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from . import models
from .department_mapping import DEPARTMENT_NAMES, SERVICE_CATEGORIES, department_for_category
from .security import hash_password


@dataclass(frozen=True)
class LoginCredential:
    name: str
    email: str
    password: str
    role: str
    service_category: str | None = None
    department: str | None = None


ADMIN_ACCOUNTS: tuple[LoginCredential, ...] = (
    LoginCredential("Ward Control Room", "admin@civicfix.local", "Admin@12345", models.Role.ADMIN.value, None, "Control Room"),
    LoginCredential("Roads Administrator", "roads.admin@civicfix.local", "CivicFix#Admin01", models.Role.ADMIN.value, None, "Road Administration"),
    LoginCredential("Sanitation Administrator", "sanitation.admin@civicfix.local", "CivicFix#Admin02", models.Role.ADMIN.value, None, "Sanitation Administration"),
    LoginCredential("Public Lighting Administrator", "lighting.admin@civicfix.local", "CivicFix#Admin03", models.Role.ADMIN.value, None, "Electrical Administration"),
    LoginCredential("Water Services Administrator", "water.admin@civicfix.local", "CivicFix#Admin04", models.Role.ADMIN.value, None, "Water Administration"),
)

WORKER_ACCOUNTS: tuple[LoginCredential, ...] = (
    LoginCredential("Pothole Worker 01", "pothole.worker01@civicfix.local", "CivicFix#Pothole01", models.Role.FIELD_OFFICER.value, "pothole", department_for_category("pothole")),
    LoginCredential("Pothole Worker 02", "pothole.worker02@civicfix.local", "CivicFix#Pothole02", models.Role.FIELD_OFFICER.value, "pothole", department_for_category("pothole")),
    LoginCredential("Garbage Worker 01", "garbage.worker01@civicfix.local", "CivicFix#Garbage01", models.Role.FIELD_OFFICER.value, "garbage", department_for_category("garbage")),
    LoginCredential("Garbage Worker 02", "garbage.worker02@civicfix.local", "CivicFix#Garbage02", models.Role.FIELD_OFFICER.value, "garbage", department_for_category("garbage")),
    LoginCredential("Streetlight Worker 01", "streetlight.worker01@civicfix.local", "CivicFix#Street01", models.Role.FIELD_OFFICER.value, "streetlight", department_for_category("streetlight")),
    LoginCredential("Streetlight Worker 02", "streetlight.worker02@civicfix.local", "CivicFix#Street02", models.Role.FIELD_OFFICER.value, "streetlight", department_for_category("streetlight")),
    LoginCredential("Drainage Worker 01", "drainage.worker01@civicfix.local", "CivicFix#Drainage01", models.Role.FIELD_OFFICER.value, "drainage", department_for_category("drainage")),
    LoginCredential("Drainage Worker 02", "drainage.worker02@civicfix.local", "CivicFix#Drainage02", models.Role.FIELD_OFFICER.value, "drainage", department_for_category("drainage")),
    LoginCredential("Road Infrastructure Worker 01", "roadinfra.worker01@civicfix.local", "CivicFix#RoadInfra01", models.Role.FIELD_OFFICER.value, "road_infrastructure", department_for_category("road_infrastructure")),
    LoginCredential("Road Infrastructure Worker 02", "roadinfra.worker02@civicfix.local", "CivicFix#RoadInfra02", models.Role.FIELD_OFFICER.value, "road_infrastructure", department_for_category("road_infrastructure")),
    LoginCredential("Water Supply Worker 01", "watersupply.worker01@civicfix.local", "CivicFix#Water01", models.Role.FIELD_OFFICER.value, "water_supply", department_for_category("water_supply")),
    LoginCredential("Water Supply Worker 02", "watersupply.worker02@civicfix.local", "CivicFix#Water02", models.Role.FIELD_OFFICER.value, "water_supply", department_for_category("water_supply")),
)


def provision_accounts(db: Session) -> None:
    """Create demo admins + exactly two worker accounts per service category.

    Existing users are updated only for role/routing metadata. Existing passwords
    are preserved once a real account has been changed from its demo default.
    """
    for account in ADMIN_ACCOUNTS:
        user = db.query(models.User).filter(models.User.email == account.email).first()
        if user is None:
            user = models.User(
                name=account.name,
                email=account.email,
                role=account.role,
                department=account.department,
                password_hash=hash_password(account.password),
                is_active=True,
                availability_status="available",
            )
            db.add(user)
        else:
            user.name = account.name
            user.role = account.role
            user.department = account.department
            user.is_active = True
            if not user.password_hash:
                user.password_hash = hash_password(account.password)

    for account in WORKER_ACCOUNTS:
        user = db.query(models.User).filter(models.User.email == account.email).first()
        if user is None:
            user = models.User(
                name=account.name,
                email=account.email,
                role=account.role,
                department=account.department,
                service_category=account.service_category,
                availability_status="available",
                is_active=True,
                password_hash=hash_password(account.password),
            )
            db.add(user)
        else:
            user.name = account.name
            user.role = account.role
            user.department = account.department
            user.service_category = account.service_category
            user.is_active = True
            if not user.password_hash:
                user.password_hash = hash_password(account.password)

    db.flush()


def credentials_text() -> str:
    lines: list[str] = []
    lines.append("CIVICFIX DEMO LOGIN CREDENTIALS")
    lines.append("=" * 72)
    lines.append("FOR HACKATHON / DEMO DEPLOYMENT ONLY")
    lines.append("Change all passwords before real production use.")
    lines.append("")
    lines.append(f"ADMIN ACCOUNTS ({len(ADMIN_ACCOUNTS)})")
    lines.append("-" * 72)
    for account in ADMIN_ACCOUNTS:
        lines.append(f"Name      : {account.name}")
        lines.append(f"Email     : {account.email}")
        lines.append(f"Password  : {account.password}")
        lines.append(f"Role      : {account.role}")
        lines.append(f"Department: {account.department or 'Control Room'}")
        lines.append("")

    lines.append(f"FIELD WORKER ACCOUNTS ({len(WORKER_ACCOUNTS)})")
    lines.append("-" * 72)
    for account in WORKER_ACCOUNTS:
        lines.append(f"Name          : {account.name}")
        lines.append(f"Email         : {account.email}")
        lines.append(f"Password      : {account.password}")
        lines.append(f"Role          : {account.role}")
        lines.append(f"Issue Category : {account.service_category}")
        lines.append(f"Service Unit  : {account.department}")
        lines.append("")

    lines.append("ROUTING MODEL")
    lines.append("-" * 72)
    for category, department in zip(SERVICE_CATEGORIES, DEPARTMENT_NAMES):
        workers = [w.email for w in WORKER_ACCOUNTS if w.service_category == category]
        lines.append(f"{category:20} -> {department:28} -> {', '.join(workers)}")
    lines.append("")
    lines.append("AUTO-ROUTING RULE")
    lines.append("- " + "The AI classification chooses the service category.")
    lines.append("- " + "CivicFix picks an active worker from that exact category.")
    lines.append("- " + "Up to MAX_ACTIVE_CASES_PER_WORKER active cases are allowed per worker.")
    lines.append("- " + "If both workers reach capacity, the case stays OPEN and enters the category queue.")
    return "\n".join(lines) + "\n"
