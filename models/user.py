"""models/user.py — User model with role-based access control."""
import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum
from db.base import Base


class UserRole(str, enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    INTERNAL_AUDITOR = "internal_auditor"
    AUDIT_MANAGER = "audit_manager"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    EXECUTIVE_VIEWER = "executive_viewer"
    EXTERNAL_AUDITOR = "external_auditor"
    CONNECTOR_SERVICE = "connector_service"
    PROCESS_OWNER = "process_owner"


class User(Base):
    __tablename__ = "users"
    org_id = Column(String(50), nullable=False, index=True, default="default-org")
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(
        Enum(UserRole, name="userrole", create_constraint=True),
        nullable=False,
        default=UserRole.INTERNAL_AUDITOR,
    )
    is_active = Column(Boolean, default=True)

