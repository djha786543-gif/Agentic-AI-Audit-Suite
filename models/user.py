"""models/user.py — fixed to import from db.base not db.base_class"""
from sqlalchemy import Column, Integer, String, Boolean
from db.base import Base

class User(Base):
    __tablename__ = "users"
    org_id = Column(String(50), nullable=False, index=True, default="default-org")
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
