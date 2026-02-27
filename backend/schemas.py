from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List
from models import ControlMode

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class PairCodeResponse(BaseModel):
    pair_code: str
    expires_in: int

class DevicePairRequest(BaseModel):
    pair_code: str
    device_name: str
    platform: str
    agent_version: str

class DevicePairResponse(BaseModel):
    device_token: str
    device_id: int

class DeviceResponse(BaseModel):
    id: int
    name: Optional[str]
    armed: bool
    threshold: float
    cooldown_sec: int
    control_mode: str
    last_seen_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)

class DeviceUpdateRequest(BaseModel):
    armed: Optional[bool] = None
    threshold: Optional[float] = None
    cooldown_sec: Optional[int] = None
    control_mode: Optional[ControlMode] = None

class EventCreateRequest(BaseModel):
    event_type: str = "PERSON"
    confidence: float
    happened_at: datetime

class EventCreateResponse(BaseModel):
    event_id: str

class SnapshotUploadResponse(BaseModel):
    success: bool
    image_url: str

class EventResponse(BaseModel):
    id: str
    device_id: int
    event_type: str
    confidence: float
    happened_at: datetime
    created_at: datetime
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class OTPVerifyRequest(BaseModel):
    otp_code: str

class OTPVerifyResponse(BaseModel):
    success: bool
    chat_id: str
