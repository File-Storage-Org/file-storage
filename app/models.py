from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, UUID, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from .database import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    file = Column(String, nullable=False)
    file_uuid = Column(UUID, nullable=False)
    user_id = Column(Integer, nullable=False)
    format = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    should_delete = Column(Boolean, default=False)

    favorites = relationship(
        "Favorite", back_populates="files", cascade="all, delete-orphan"
    )
    scheduled_jobs = relationship(
        "ScheduledJob", back_populates="files", cascade="all, delete-orphan"
    )


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)

    files = relationship("File", back_populates="favorites")


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    job_id = Column(UUID, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("File", back_populates="scheduled_jobs")
