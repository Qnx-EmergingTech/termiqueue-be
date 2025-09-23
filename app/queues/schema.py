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