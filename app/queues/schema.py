from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class QueueJoinResponse(BaseModel):
    id: str
    message: str
    ticket_number: int
    queue_number: int
    is_privileged: bool
    joined_at: datetime


class QueueLeaveResponse(BaseModel):
    id: str
    message: str


class QueueStatusResponse(BaseModel):
    ticket_number: int
    queue_number: int
    is_privileged: bool
    status: str
    joined_at: datetime


class CreateQueueInfo(BaseModel):
    destination: str
    priority_seat: Optional[int] = 5


class QueueInfoResponse(BaseModel):
    id: str
    destination: str
    priority_seat: int
    capacity: int | None = None
    bus_id: str | None = None
    eta: str | None = None
    status: str | None = None
    created_at: datetime


class GeofenceCheck(BaseModel):
    lat: float
    lon: float
