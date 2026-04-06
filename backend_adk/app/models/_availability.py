# app/models/_availability.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from app.db._database import Base


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    availability_type = Column(String, default="available")  # available / on-leave / sick / training
    notes = Column(String, nullable=True)
