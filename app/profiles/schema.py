from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from datetime import datetime


class UserProfile(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    birthdate: datetime
    is_privileged: bool = False
    in_queue: bool = False
    user_type: Literal["normal_user", "bus_attendant", "admin"] = "normal_user"


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    birthdate: Optional[datetime] = None
    is_privileged: Optional[bool] = None
    in_queue: Optional[bool] = None
    # user_type: Optional[Literal["normal_user", "bus_attendant", "admin"]] = None

    def to_update_dict(self):
        return self.dict(exclude_unset=True)


class CreatUserAccountRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    voucher_code: Optional[str] = None


class CreateUserAccountResponse(BaseModel):
    id: str


class SignupRequest(BaseModel):
    username: str


class UsernameLoginRequest(BaseModel):
    username: str
    password: str


class UserProfileResponse(BaseModel):
    id: str
    message: str


class FCMToken(BaseModel):
    fcm_token: str


class TripSummary(BaseModel):
    id: str
    bus_id: str
    bus_number: str
    plate_number: str
    origin: str
    destination: str
    ticket_number: int
    boarded_at: datetime
    departed_at: datetime
    finished_at: Optional[datetime] = None


class TripHistoryResponse(BaseModel):
    trips: list[TripSummary]
