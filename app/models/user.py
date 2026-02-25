from sqlalchemy import Column, Integer, String, Boolean, Enum
import enum
from db.base_class import Base

class UserRole(str, enum.Enum):
    INTERNAL_AUDITOR = "internal_auditor"
    EXTERNAL_AUDITOR = "external_auditor"
    CONNECTOR_SERVICE = "connector_service"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CONNECTOR_SERVICE)
    is_active = Column(Boolean, default=True)
