from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Location(BaseModel):
    lat: float
    lon: float


class BusInfo(BaseModel):
    plate_number: str
    priority_seat: int
    capacity: int
    status: Optional[str] = None
    current_location: Optional[Location] = None


class BusInfoResponse(BaseModel):
    id: str
    plate_number: str
    priority_seat: int
    capacity: int
    status: Optional[str] = None
    current_location: Optional[Location] = None
    created_at: datetime
    updated_at: datetime
