from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import firestore
from app.core.dependencies import get_firestore, verify_token
from app.geofence.service import GeofenceService
from app.geofence.schema import GeofenceConfig

router = APIRouter(prefix="/geofence", tags=["geofence"])


def get_geofence_service(
    db: firestore.Client = Depends(get_firestore),
) -> GeofenceService:
    return GeofenceService(db)


@router.get("/", response_model=GeofenceConfig)
def get_geofence_config(
    service: GeofenceService = Depends(get_geofence_service),
):
    return service.get_geofence()


@router.put("/")
def update_geofence_config(
    config: GeofenceConfig,
    service: GeofenceService = Depends(get_geofence_service),
    uid: str = Depends(verify_token),
):
    profile_ref = service.db.collection("profiles").document(uid)
    profile_snapshot = profile_ref.get()

    if not profile_snapshot.exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profile_snapshot.to_dict()

    if profile.get("user_type") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin users can update geofence configuration",
        )

    service.update_geofence(config)
    return {"message": "Geofence updated successfully"}
