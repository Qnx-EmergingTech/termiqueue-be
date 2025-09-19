from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from app.core.geolocation_service import GeolocationService
from app.core.dependencies import get_firestore, verify_token
from app.queues.service import QueueService

router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("/check-geofence")
def check_geofence(
    lat: float,
    lon: float,
):
    geolocation_service = GeolocationService()
    if geolocation_service.is_within_geofence(lat, lon):
        return {"can_join": True, "message": "User is within the geofence."}
    else:
        return {"can_join": False, "message": "User is outside the geofence."}


@router.post("/{queue_id}/join")
def join_queue(
    # lat: float,
    # lon: float,
    queue_id: str,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    # if not is_within_geofence(lat, lon):
    #     raise HTTPException(status_code=403, detail="User is outside the geofence.")
    service = QueueService(db)
    ticket_number = service.join_queue(uid, queue_id)
    return {
        "message": "User has joined the queue successfully.",
        "ticket_number": ticket_number,
    }


@router.post("/{queue_id}/leave")
def leave_queue(
    queue_id: str,
    db: firestore.Client = Depends(get_firestore),
    uid: str = Depends(verify_token),
):
    service = QueueService(db)
    service.leave_queue(uid, queue_id)
    return {"message": "User has left the queue successfully."}
