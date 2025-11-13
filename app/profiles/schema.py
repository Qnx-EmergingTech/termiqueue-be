from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class UserProfile(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    address: str
    birthdate: datetime
    is_privileged: bool
    in_queue: bool = False
    user_type: Literal["normal_user", "bus_attendant"] = "normal_user"


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    address: Optional[str] = None
    birthdate: Optional[datetime] = None
    is_privileged: Optional[bool] = None
    in_queue: Optional[bool] = None
    user_type: Optional[Literal["normal_user", "bus_attendant"]] = None

    def to_update_dict(self):
        return self.dict(exclude_unset=True)


class UserProfileResponse(BaseModel):
    id: str
    message: str
