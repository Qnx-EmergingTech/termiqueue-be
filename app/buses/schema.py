from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class Location(BaseModel):
    lat: float
    lon: float


class BusInfo(BaseModel):
    plate_number: str
    bus_name: str
    bus_number: str
    priority_seat: int
    capacity: int
    origin: str
    destination: str
    status: Optional[Literal["available", "active", "offline"]] = "available"
    current_location: Optional[Location] = None
    attendant_id: Optional[str] = None
    attendant_name: Optional[str] = None


class BusInfoResponse(BaseModel):
    id: str
    plate_number: str
    bus_name: str
    bus_number: str
    priority_seat: int
    capacity: int
    origin: str
    destination: str
    status: Optional[str] = None
    current_location: Optional[Location] = None
    attendant_id: Optional[str] = None
    attendant_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BusInfoUpdate(BaseModel):
    plate_number: Optional[str] = None
    bus_name: Optional[str] = None
    bus_number: Optional[str] = None
    priority_seat: Optional[int] = None
    capacity: Optional[int] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: Optional[Literal["available", "active", "offline"]] = None
    current_location: Optional[Location] = None

    def to_update_dict(self):
        return self.dict(exclude_unset=True)


class ClaimBusResponse(BaseModel):
    id: str
    message: str
    attendant_id: str
    attendant_name: str


class BusLocationUpdate(BaseModel):
    lat: float
    lon: float


class BusArrivalRequest(BaseModel):
    pass


class QRScanRequest(BaseModel):
    qr_json: str
