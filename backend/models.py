import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum
from database import Base

class ControlMode(str, enum.Enum):
    BOTH = "BOTH"
    DASHBOARD_ONLY = "DASHBOARD_ONLY"
    TELEGRAM_ONLY = "TELEGRAM_ONLY"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    devices = relationship("Device", back_populates="owner")
    telegram_link = relationship("TelegramLink", uselist=False, back_populates="user")
    events = relationship("Event", back_populates="user")
    pair_codes = relationship("PairCode", back_populates="user")

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    agent_version = Column(String, nullable=True)
    
    armed = Column(Boolean, default=True, nullable=False)
    threshold = Column(Float, default=0.5, nullable=False)
    cooldown_sec = Column(Integer, default=5, nullable=False)
    control_mode = Column(String, default=ControlMode.BOTH.value, nullable=False)
    
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    owner = relationship("User", back_populates="devices")
    events = relationship("Event", back_populates="device")

class PairCode(Base):
    __tablename__ = "pair_codes"

    id = Column(Integer, primary_key=True, index=True)
    pair_code = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="pair_codes")

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    event_type = Column(String, default="PERSON", nullable=False)
    confidence = Column(Float, nullable=False)
    happened_at = Column(DateTime, nullable=False) # Agent time
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False) # Server time
    
    image_filename = Column(String, nullable=True)

    device = relationship("Device", back_populates="events")
    user = relationship("User", back_populates="events")

class TelegramLink(Base):
    __tablename__ = "telegram_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    chat_id = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="telegram_link")

class TelegramOTP(Base):
    __tablename__ = "telegram_otps"
    
    id = Column(Integer, primary_key=True, index=True)
    otp_code = Column(String, unique=True, index=True, nullable=False)
    chat_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)

class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"
    
    id = Column(Integer, primary_key=True, index=True)
    update_id = Column(Integer, unique=True, index=True, nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
